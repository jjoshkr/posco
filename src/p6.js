
/* =========================================================
   10. AUDIO ENGINE (Web Audio API only)
   master chain: session bus -> fade -> compressor -> master gain -> out
   ========================================================= */
const AU = { ac:null, comp:null, master:null, verb:null, white:null, pink:null, sess:null, events:[], muted:false };
const mtof = m => 440 * Math.pow(2, (m - 69) / 12);
function auInit() {
  if (AU.ac) return;
  const ac = AU.ac = new (window.AudioContext || window.webkitAudioContext)();
  AU.comp = ac.createDynamicsCompressor();
  AU.comp.threshold.value = -20; AU.comp.ratio.value = 3; AU.comp.attack.value = .01; AU.comp.release.value = .25;
  AU.master = ac.createGain(); AU.master.gain.value = AU.muted ? 0 : .85;
  AU.comp.connect(AU.master); AU.master.connect(ac.destination);
  // generated reverb impulse
  const r = rng(5), sr = ac.sampleRate, len = Math.floor(sr * 2.4), ir = ac.createBuffer(2, len, sr);
  for (let ch = 0; ch < 2; ch++) { const d = ir.getChannelData(ch); for (let i = 0; i < len; i++) d[i] = (r() * 2 - 1) * Math.pow(1 - i / len, 3.2); }
  AU.verb = ac.createConvolver(); AU.verb.buffer = ir;
  const vg = ac.createGain(); vg.gain.value = .32; AU.verb.connect(vg); vg.connect(AU.comp);
  // noise buffers
  const wl = sr * 2, wb = ac.createBuffer(1, wl, sr), wd = wb.getChannelData(0); for (let i = 0; i < wl; i++) wd[i] = r() * 2 - 1;
  const pl = sr * 4, pb = ac.createBuffer(1, pl, sr), pd = pb.getChannelData(0);
  let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
  for (let i = 0; i < pl; i++) { const w = r() * 2 - 1;
    b0 = .99886*b0 + w*.0555179; b1 = .99332*b1 + w*.0750759; b2 = .969*b2 + w*.153852; b3 = .8665*b3 + w*.3104856; b4 = .55*b4 + w*.5329522; b5 = -.7616*b5 - w*.016898;
    pd[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * .5362) * .11; b6 = w * .115926; }
  AU.white = wb; AU.pink = pb;
  buildEvents();
}
const A = {
  G: (v = 0) => { const g = AU.ac.createGain(); g.gain.value = v; return g; },
  O: (type, f) => { const o = AU.ac.createOscillator(); o.type = type; o.frequency.value = f; return o; },
  F: (type, f, q = .7) => { const b = AU.ac.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; return b; },
  N: (buf, loop = false) => { const n = AU.ac.createBufferSource(); n.buffer = buf; n.loop = loop; return n; },
  chain: (...n) => { for (let i = 0; i < n.length - 1; i++) n[i].connect(n[i+1]); return n[n.length - 1]; },
  perc: (g, at, peak, a, d) => { g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(peak, at + a); g.gain.exponentialRampToValueAtTime(.0001, at + a + d); },
  sus: (g, at, end, peak, att, rel) => { att = Math.min(att, (end - at) * .4); rel = Math.min(rel, (end - at) * .5);
    g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(peak, at + att); g.gain.setValueAtTime(peak, end - rel); g.gain.linearRampToValueAtTime(0, end); },
  // piecewise automation in timeline time, safe when starting mid-way
  auto: (param, pts, o) => { const now = o.at; let prev = pts[0];
    for (const p of pts) if (o.s.base + p[0] <= now) prev = p;
    const nxt = pts.find(p => o.s.base + p[0] > now);
    let v0 = prev[1]; if (nxt && prev !== nxt) { const k = clamp((now - o.s.base - prev[0]) / (nxt[0] - prev[0])); v0 = lerp(prev[1], nxt[1], k); }
    param.setValueAtTime(v0, now);
    pts.forEach(p => { const at = o.s.base + p[0]; if (at > now) param.linearRampToValueAtTime(p[1], at); }); }
};
function play(o, src, at, end) { src.start(at); src.stop(end + .05); o.s.srcs.push(src); }

function buildEvents() {
  const ev = AU.events = [];
  const add = (t, d, f, long = false) => ev.push({ t, d, f, long });
  const out = o => o.s.bus, send = o => o.s.send;
  // --- tonal helpers
  const tone = (type, f, peak, a, d, toSend = 0, f2 = null) => o => {
    const os = A.O(type, f), g = A.G(); os.frequency.setValueAtTime(f, o.at); if (f2) os.frequency.exponentialRampToValueAtTime(f2, o.at + a + d);
    A.chain(os, g, out(o)); if (toSend) { const sg = A.G(toSend); g.connect(sg); sg.connect(send(o)); }
    A.perc(g, o.at, peak, a, d); play(o, os, o.at, o.at + a + d);
  };
  const noiseHit = (ftype, f, q, peak, a, d, f2 = null, toSend = 0) => o => {
    const n = A.N(AU.white, true), fl = A.F(ftype, f, q), g = A.G(); fl.frequency.setValueAtTime(f, o.at);
    if (f2) fl.frequency.exponentialRampToValueAtTime(f2, o.at + a + d);
    A.chain(n, fl, g, out(o)); if (toSend) { const sg = A.G(toSend); g.connect(sg); sg.connect(send(o)); }
    A.perc(g, o.at, peak, a, d); play(o, n, o.at, o.at + a + d);
  };
  // --- MUSIC: pad I–V–vi–IV in C major, one chord per 4 s
  const CH = [[60,64,67],[55,59,62],[57,60,64],[53,57,60]], ROOT = [36,43,45,41];
  for (let i = 0; i < 20; i++) {
    const t0 = i * 4, ch = CH[i % 4], bright = t0 >= 66, lvl = t0 < 4 ? .010 : (t0 < 56 ? .016 : .019);
    add(t0, 4.7, o => {
      const lp = A.F('lowpass', bright ? 1600 : 950, .6), g = A.G();
      A.chain(lp, g, out(o)); const sg = A.G(.25); g.connect(sg); sg.connect(send(o));
      if (bright) { lp.frequency.setValueAtTime(1600, o.at); lp.frequency.linearRampToValueAtTime(3200, o.end); }
      A.sus(g, o.at, o.end, 1, o.off ? .2 : 1.2, .9);
      ch.forEach(m => [['sine', 0], ['triangle', 7], ['triangle', -7]].concat(bright ? [['sine', 1200]] : []).forEach(([ty, c]) => {
        const os = A.O(ty, mtof(m)); os.detune.value = c; const og = A.G(lvl); A.chain(os, og, lp); play(o, os, o.at, o.end); }));
    }, true);
    if (t0 >= 12) add(t0, 4.2, o => { const os = A.O('sine', mtof(ROOT[i % 4])), g = A.G(); A.chain(os, g, out(o)); A.sus(g, o.at, o.end, t0 < 56 ? .07 : .09, .08, .5); play(o, os, o.at, o.end); }, true);
    // plucked arpeggio from 14 s (16th notes)
    if (t0 >= 12) for (let k = 0; k < 16; k++) {
      const tt = t0 + k * .25; if (tt < 14 || tt > 79.6) continue;
      const pat = [0,1,2,1, 0,2,1,2, 0,1,2,0, 2,1,0,1], oct = (k % 8 > 3) ? 24 : 12, m = ch[pat[k]] + oct;
      const lv = (tt < 18 ? lerp(.012, .03, (tt - 14) / 4) : .03) * (k % 4 === 0 ? 1.25 : 1) * (tt > 67 ? 1.15 : 1);
      add(tt, .4, o => { const os = A.O('triangle', mtof(m)), lp = A.F('lowpass', tt > 67 ? 4200 : 2600), g = A.G(); A.chain(os, lp, g, out(o));
        const sg = A.G(.3); g.connect(sg); sg.connect(send(o)); A.perc(g, o.at, lv, .004, .34); play(o, os, o.at, o.at + .38); });
    }
  }
  // light kick/hat from 56 s; claps on 2 & 4 from 67 s
  for (let tt = 56; tt < 79.6; tt += .5) {
    const loud = tt >= 67 ? 1 : .65;
    add(tt, .4, o => { const os = A.O('sine', 140), g = A.G(); os.frequency.setValueAtTime(140, o.at); os.frequency.exponentialRampToValueAtTime(42, o.at + .3); A.chain(os, g, out(o)); A.perc(g, o.at, .22 * loud, .004, .32); play(o, os, o.at, o.at + .36); });
    add(tt + .25, .08, noiseHit('highpass', 7500, .7, .035 * loud, .002, .05));
    if (tt >= 67 && Math.round((tt - 56) * 2) % 4 === 2) add(tt, .2, noiseHit('bandpass', 1600, .9, .06, .002, .12, null, .3));
  }
  // --- AMBIENCE: wind + birds
  const wind = (lvl) => o => { const n = A.N(AU.pink, true), lp = A.F('lowpass', 650, .4), g = A.G(), lfo = A.O('sine', .17), lg2 = A.G(lvl * .5);
    A.chain(n, lp, g, out(o)); lfo.connect(lg2); lg2.connect(g.gain); A.sus(g, o.at, o.end, lvl, o.off ? .3 : 2, 1.5); play(o, n, o.at, o.end); play(o, lfo, o.at, o.end); };
  add(0, 14, wind(.11), true); add(70, 10, wind(.09), true);
  { const r = rng(21); for (let i = 0; i < 16; i++) { const tt = .9 + r() * 8, f0 = 2400 + r() * 1400;
      for (let j = 0; j < 2 + Math.floor(r() * 2); j++) add(tt + j * .09, .08, o => { const os = A.O('sine', f0), fm = A.O('sine', 38), fg = A.G(260), g = A.G();
        fm.connect(fg); fg.connect(os.frequency); os.frequency.setValueAtTime(f0, o.at); os.frequency.exponentialRampToValueAtTime(f0 * 1.45, o.at + .06);
        A.chain(os, g, out(o)); A.perc(g, o.at, .022, .006, .07); play(o, os, o.at, o.at + .09); play(o, fm, o.at, o.at + .09); }); } }
  // --- PLANT HUM 6–56 s, swells while zoomed in
  add(6, 50, o => { const lp = A.F('lowpass', 190, .8), g = A.G(); A.chain(lp, g, out(o));
    [55, 55.4, 110.3].forEach(f => { const os = A.O('sawtooth', f), og = A.G(f > 100 ? .25 : .5); A.chain(os, og, lp); play(o, os, o.at, o.end); });
    const pts = [[6, 0], [8, .05]]; STOPS.forEach(st => { pts.push([st.s + .3, .05], [st.s + 1.3, .085], [st.e - .3, .085]); }); pts.push([50.5, .05], [55, .04], [56, 0]);
    A.auto(g.gain, pts, o); }, true);
  // --- CAMERA WHOOSHES
  [6.0, 14.0, 21.0, 29.0, 36.0, 43.0, 50.0, 55.7, 70.0].forEach(tt => add(tt, 1.1, o => {
    const n = A.N(AU.white, true), bp = A.F('bandpass', 300, 1.2), g = A.G(); A.chain(n, bp, g, out(o));
    bp.frequency.setValueAtTime(300, o.at); bp.frequency.exponentialRampToValueAtTime(2200, o.at + .55); bp.frequency.exponentialRampToValueAtTime(500, o.at + 1.1);
    g.gain.setValueAtTime(0, o.at); g.gain.linearRampToValueAtTime(.07, o.at + .5); g.gain.linearRampToValueAtTime(0, o.at + 1.1); play(o, n, o.at, o.at + 1.1); }));
  // --- HAZARD STOPS: ping / caution pulse / ding
  const caution = tt => [0, .5].forEach(dt => { add(tt + dt, .25, tone('triangle', 330, .07, .02, .2)); add(tt + dt + .24, .25, tone('triangle', 262, .07, .02, .22)); });
  STOPS.forEach(st => {
    add(st.s + .8, .6, tone('sine', 880, .12, .004, .5, .25));
    add(st.s + .8, .3, tone('sine', 1760, .03, .004, .25));
    add(GREEN_AT(st), .7, tone('sine', 1318.5, .09, .005, .4, .3));
    add(GREEN_AT(st) + .12, .9, tone('sine', 1760, .09, .005, .6, .3));
    add(GREEN_AT(st) + .12, .9, tone('triangle', 1760, .025, .005, .4));
  });
  caution(15.6); caution(24.0); caution(31.25); caution(38.6);
  add(16.5, .3, noiseHit('bandpass', 3200, 2, .05, .01, .25, 900));          // valve closes
  add(22.4, 1.6, tone('sine', 70, .08, .5, 1.0, 0, 95));                    // reactor heat rumble
  add(24.0, .7, tone('sine', 420, .07, .01, .6, 0, 70));                    // power-down drop
  add(25.45, .5, tone('sine', 120, .28, .004, .35, .3, 48));                // interlock slam
  add(25.45, .3, noiseHit('lowpass', 900, .7, .12, .002, .18, 200));
  { const r = rng(9); for (let i = 0; i < 7; i++) add(31.2 + r() * .3, .05, noiseHit('highpass', 5000, .7, .05, .001, .03)); }  // spark crackle
  add(31.6, 1.4, o => { const n = A.N(AU.white, true), bp = A.F('bandpass', 400, 1.4), g = A.G(); A.chain(n, bp, g, out(o));
    bp.frequency.setValueAtTime(400, o.at); bp.frequency.exponentialRampToValueAtTime(1800, o.end); A.sus(g, o.at, o.end, .05, .2, .4); play(o, n, o.at, o.end); });  // dust extraction
  add(38.6, .1, tone('sine', 1200, .05, .005, .08)); add(38.78, .1, tone('sine', 1200, .05, .005, .08));  // UV/IR detect beeps
  add(44.2, 5.4, o => { const os = A.O('sawtooth', 180), lp = A.F('lowpass', 800), g = A.G(), trem = A.O('sine', 23), tg = A.G(.006);
    trem.connect(tg); tg.connect(g.gain); A.chain(os, lp, g, out(o)); A.sus(g, o.at, o.end, .016, .6, .8); play(o, os, o.at, o.end); play(o, trem, o.at, o.end); }, true);  // drone
  // --- PERMIT CHIPS: five rising ticks
  CHIPS.forEach((c, i) => { const f = 900 * Math.pow(1.122, i * 2); add(50.9 + i * .55, .2, tone('sine', f, .08, .003, .12, .2)); add(50.9 + i * .55, .2, tone('triangle', f * 2, .02, .003, .08)); });
  // --- CERTIFICATION
  [56.8, 57.0, 57.3].forEach(tt => add(tt, .5, tone('sine', 1567, .03, .01, .4, .3)));   // power icons light up
  [60.3, 61.3, 62.4, 66.2, 68.3].forEach(tt => add(tt, .15, tone('triangle', 1400, .04, .002, .08)));
  add(60.2, .9, tone('sine', 300, .03, .1, .7, 0, 620)); add(62.2, .9, tone('sine', 300, .03, .1, .7, 0, 640));
  add(64.0, .7, noiseHit('bandpass', 600, 1.2, .05, .2, .4, 2400));
  { const r = rng(14); for (let i = 0; i < 6; i++) add(64.6 + i * .08, .1, tone('sine', 2600 + r() * 2200, .025, .003, .07, .4)); }
  add(65.5, .5, tone('sine', 110, .22, .004, .32, .35, 50)); add(65.5, .2, noiseHit('lowpass', 700, .7, .08, .002, .12));
  add(67.0, 1.3, tone('sine', 820, .035, .1, 1.15, .2, 260));              // credit bar drop
  for (let i = 0; i < 12; i++) add(67.05 + i * .1, .06, tone('triangle', 1800 - i * 60, .018, .002, .04));
  // stamp: deep thud + reverb tail, then brass-like chord
  add(68.5, .9, tone('sine', 92, .5, .004, .7, .6, 36));
  add(68.5, .4, noiseHit('lowpass', 260, .7, .25, .002, .3, 90, .5));
  add(68.62, 1.9, o => { const lp = A.F('lowpass', 400, 1.1), g = A.G(); A.chain(lp, g, out(o)); const sg = A.G(.4); g.connect(sg); sg.connect(send(o));
    lp.frequency.setValueAtTime(400, o.at); lp.frequency.exponentialRampToValueAtTime(3400, o.at + .25); lp.frequency.exponentialRampToValueAtTime(1600, o.end);
    A.sus(g, o.at, o.end, 1, .03, 1.0);
    [60, 64, 67, 72, 48].forEach(m => [-8, 8].forEach(dt => { const os = A.O('sawtooth', mtof(m)); os.detune.value = dt; const og = A.G(.022); A.chain(os, og, lp); play(o, os, o.at, o.end); }));
  });
  // --- CELEBRATION: cheer swells, claps, sparkles
  add(70.6, 9.4, o => { const r = rng(42);
    [[1100, .8], [2400, 1.1]].forEach(([f, q], j) => { const n = A.N(AU.pink, true), bp = A.F('bandpass', f, q), g = A.G(); A.chain(n, bp, g, out(o));
      const pts = [[70.6, 0], [71.4, .16]]; for (let tt = 71.6; tt < 79; tt += .3) pts.push([tt, .09 + r() * .12]); pts.push([79.2, .06], [80, 0]);
      A.auto(g.gain, pts, o); play(o, n, o.at, o.end); }); }, true);
  { const r = rng(55); for (let i = 0; i < 44; i++) { const tt = 70.9 + r() * 8.2, lv = .05 + r() * .06, f = 1200 + r() * 900;
      [0, .008, .017].forEach(dt => add(tt + dt, .1, noiseHit('bandpass', f, 1.1, lv, .001, .06))); } }
  { const r = rng(66); for (let i = 0; i < 50; i++) add(70.9 + r() * 8.4, .08, tone('sine', 2600 + r() * 2600, .018, .003, .06, .5)); }
  ev.sort((a, b) => a.t - b.t);
}
// session = one continuous playback run from timeline time T0
function auStart(T0) {
  if (!AU.ac) return; auStop();
  const ac = AU.ac, now = ac.currentTime + .04;
  const s = { T0, base: now - T0, srcs: [], idx: 0 };
  s.bus = ac.createGain(); s.send = ac.createGain(); s.fade = ac.createGain(); s.fade2 = ac.createGain();
  s.bus.connect(s.fade); s.fade.connect(AU.comp); s.send.connect(s.fade2); s.fade2.connect(AU.verb);
  // global fade-out over the last 1.5 s
  [s.fade, s.fade2].forEach(f => { const v0 = T0 < 78.5 ? 1 : clamp(1 - (T0 - 78.5) / 1.5);
    f.gain.setValueAtTime(v0, now); if (T0 < 78.5) f.gain.setValueAtTime(1, s.base + 78.5); f.gain.linearRampToValueAtTime(0, s.base + 80); });
  AU.sess = s;
}
function auStop() {
  const s = AU.sess; if (!s) return; AU.sess = null;
  const t = AU.ac.currentTime;
  [s.fade, s.fade2].forEach(f => { f.gain.cancelScheduledValues(t); f.gain.setValueAtTime(f.gain.value, t); f.gain.linearRampToValueAtTime(0, t + .06); });
  setTimeout(() => { s.srcs.forEach(n => { try { n.stop(); } catch (e) {} }); try { s.fade.disconnect(); s.fade2.disconnect(); } catch (e) {} }, 120);
}
function auTick(tl) {
  const s = AU.sess; if (!s) return;
  const ev = AU.events, horizon = tl + .3;
  while (s.idx < ev.length && ev[s.idx].t <= horizon) {
    const e = ev[s.idx++];
    if (e.t + e.d <= s.T0) continue;                 // already over
    if (e.t < s.T0 - .05 && !e.long) continue;       // short one-shots are skipped when seeking past them
    const at = Math.max(AU.ac.currentTime + .01, s.base + e.t), end = s.base + e.t + e.d;
    if (end - at < .03) continue;
    try { e.f({ s, at, end, off: Math.max(0, s.T0 - e.t) }); } catch (err) { console.warn(err); }
  }
}
function auMute(m) { AU.muted = m; if (AU.master) AU.master.gain.setTargetAtTime(m ? 0 : .85, AU.ac.currentTime, .03); }
