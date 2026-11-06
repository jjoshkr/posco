function buildEvents() {
  const ev = AU.events = [];
  const add = (t, d, f, long = false) => ev.push({ t, d, f, long });
  const out = o => o.s.bus, send = o => o.s.send;
  const tone = (type, f, peak, a, d, toSend = 0, f2 = null) => o => {
    const os = A.O(type, f), g2 = A.G(); os.frequency.setValueAtTime(f, o.at); if (f2) os.frequency.exponentialRampToValueAtTime(f2, o.at + a + d);
    A.chain(os, g2, out(o)); if (toSend) { const sg = A.G(toSend); g2.connect(sg); sg.connect(send(o)); }
    A.perc(g2, o.at, peak, a, d); play(o, os, o.at, o.at + a + d);
  };
  const noiseHit = (ftype, f, q, peak, a, d, f2 = null, toSend = 0) => o => {
    const n = A.N(AU.white, true), fl = A.F(ftype, f, q), g2 = A.G(); fl.frequency.setValueAtTime(f, o.at);
    if (f2) fl.frequency.exponentialRampToValueAtTime(f2, o.at + a + d);
    A.chain(n, fl, g2, out(o)); if (toSend) { const sg = A.G(toSend); g2.connect(sg); sg.connect(send(o)); }
    A.perc(g2, o.at, peak, a, d); play(o, n, o.at, o.at + a + d);
  };
  // ---- music: Am - F - C - G, one chord per 4 s; dusk section darker, then opening up
  const CH = [[57, 60, 64], [53, 57, 60], [55, 60, 64], [55, 59, 62]], ROOT = [33, 29, 36, 31];
  for (let i = 0; i < Math.ceil(DUR / 4); i++) {
    const t0 = i * 4, ch = CH[i % 4], dusk = t0 < 8, bright = t0 >= 72, lvl = dusk ? .011 : (t0 < 56 ? .015 : .018);
    add(t0, 4.7, o => {
      const lp = A.F('lowpass', dusk ? 650 : (bright ? 1700 : 1100), .6), g2 = A.G();
      A.chain(lp, g2, out(o)); const sg = A.G(.3); g2.connect(sg); sg.connect(send(o));
      if (bright) { lp.frequency.setValueAtTime(1700, o.at); lp.frequency.linearRampToValueAtTime(3200, o.end); }
      A.sus(g2, o.at, o.end, 1, o.off ? .2 : 1.3, .9);
      ch.forEach(m => [['sine', 0], ['triangle', 7], ['triangle', -7]].concat(bright ? [['sine', 1200]] : []).forEach(([ty, c]) => {
        const os = A.O(ty, mtof(m)); os.detune.value = c; const og = A.G(lvl); A.chain(os, og, lp); play(o, os, o.at, o.end); }));
    }, true);
    if (t0 >= 8) add(t0, 4.2, o => { const os = A.O('sine', mtof(ROOT[i % 4] + 12)), g2 = A.G(); A.chain(os, g2, out(o)); A.sus(g2, o.at, o.end, t0 < 56 ? .07 : .09, .08, .5); play(o, os, o.at, o.end); }, true);
    // plucked arpeggio: eighths from 14 s, sixteenths from 56 s
    const stepT = t0 >= 56 ? .25 : .5;
    for (let k = 0; k * stepT < 4; k++) {
      const tt = t0 + k * stepT; if (tt < 14 || tt > 86.4) continue;
      const pat = [0, 1, 2, 1, 0, 2, 1, 2], m = ch[pat[k % 8]] + ((k % 8) > 3 ? 24 : 12);
      const lv = (tt < 18 ? lerp(.01, .026, (tt - 14) / 4) : .026) * (k % 4 === 0 ? 1.2 : 1) * (tt > 72.5 ? 1.15 : 1);
      add(tt, .4, o => { const os = A.O('triangle', mtof(m)), lp = A.F('lowpass', tt > 72.5 ? 4200 : 2500), g2 = A.G(); A.chain(os, lp, g2, out(o));
        const sg = A.G(.35); g2.connect(sg); sg.connect(send(o)); A.perc(g2, o.at, lv, .004, .36); play(o, os, o.at, o.at + .4); });
    }
  }
  // light kick / hat in the certification and celebration sections
  for (let tt = 56; tt < 86.4; tt += .5) {
    const loud = tt >= 72.5 ? 1 : .6;
    add(tt, .4, o => { const os = A.O('sine', 140), g2 = A.G(); os.frequency.setValueAtTime(140, o.at); os.frequency.exponentialRampToValueAtTime(42, o.at + .3); A.chain(os, g2, out(o)); A.perc(g2, o.at, .2 * loud, .004, .32); play(o, os, o.at, o.at + .36); });
    add(tt + .25, .08, noiseHit('highpass', 7500, .7, .03 * loud, .002, .05));
  }
  // ---- ambience: wind at dusk and at the end, plant hum during the tour
  const wind = lvl => o => { const n = A.N(AU.pink, true), lp = A.F('lowpass', 650, .4), g2 = A.G(), lfo = A.O('sine', .17), lg2 = A.G(lvl * .5);
    A.chain(n, lp, g2, out(o)); lfo.connect(lg2); lg2.connect(g2.gain); A.sus(g2, o.at, o.end, lvl, o.off ? .3 : 2, 1.5); play(o, n, o.at, o.end); play(o, lfo, o.at, o.end); };
  add(0, 14, wind(.1), true); add(81, 10, wind(.08), true);
  add(14, 42, o => { const lp = A.F('lowpass', 190, .8), g2 = A.G(); A.chain(lp, g2, out(o));
    [55, 55.4, 110.3].forEach(f => { const os = A.O('sawtooth', f), og = A.G(f > 100 ? .25 : .5); A.chain(os, og, lp); play(o, os, o.at, o.end); });
    A.auto(g2.gain, [[14, 0], [16, .05], [54, .05], [56, 0]], o); }, true);
  // ---- scan-line riser: hologram becomes the real plant
  add(4.6, 3.4, o => { const n = A.N(AU.white, true), bp = A.F('bandpass', 300, 2.5), g2 = A.G(); A.chain(n, bp, g2, out(o)); const sg = A.G(.4); g2.connect(sg); sg.connect(send(o));
    bp.frequency.setValueAtTime(300, o.at); bp.frequency.exponentialRampToValueAtTime(5200, o.end - .2); A.sus(g2, o.at, o.end, .09, 1.6, .5); play(o, n, o.at, o.end); }, true);
  add(4.6, 3.4, o => { const os = A.O('sine', 660), g2 = A.G(); os.frequency.setValueAtTime(660, o.at); os.frequency.exponentialRampToValueAtTime(1980, o.end); A.chain(os, g2, out(o)); A.sus(g2, o.at, o.end, .03, 1.8, .4); play(o, os, o.at, o.end); }, true);
  add(7.7, 1.2, tone('sine', 1318.5, .06, .01, 1.1, .5));
  add(7.85, 1.2, tone('sine', 1760, .05, .01, 1.0, .5));
  // ---- cut whooshes
  [14, 21.5, 29, 36, 43, 50, 56, 64.5, 72.5, 81, 87].forEach(tt => add(tt - .35, 1.0, o => {
    const n = A.N(AU.white, true), bp = A.F('bandpass', 300, 1.2), g2 = A.G(); A.chain(n, bp, g2, out(o));
    bp.frequency.setValueAtTime(300, o.at); bp.frequency.exponentialRampToValueAtTime(2200, o.at + .5); bp.frequency.exponentialRampToValueAtTime(500, o.at + 1.0);
    g2.gain.setValueAtTime(0, o.at); g2.gain.linearRampToValueAtTime(.06, o.at + .45); g2.gain.linearRampToValueAtTime(0, o.at + 1.0); play(o, n, o.at, o.at + 1.0); }));
  // ---- HUD reveal blips and caution pulses at each hazard point
  [14, 21.5, 29, 36, 43].forEach(t0 => {
    add(t0 + 1.0, .3, tone('sine', 1320, .05, .004, .18, .3)); add(t0 + 1.12, .3, tone('sine', 1760, .045, .004, .22, .3));
    for (let k = 0; k < 6; k++) add(t0 + 1.25 + k * .07, .05, tone('square', 2400 + k * 180, .006, .001, .03));
    [0, .45].forEach(dt => { add(t0 + 1.6 + dt, .25, tone('triangle', 330, .05, .02, .2)); add(t0 + 1.84 + dt, .25, tone('triangle', 262, .05, .02, .22)); });
  });
  // ---- permit gates: five rising ticks, then a resolving ding
  for (let i = 0; i < 5; i++) { const f = 900 * Math.pow(1.122, i * 2); add(51.1 + i * .35, .2, tone('sine', f, .07, .003, .12, .2)); add(51.1 + i * .35, .2, tone('triangle', f * 2, .018, .003, .08)); }
  add(53.0, .9, tone('sine', 1318.5, .07, .005, .5, .3)); add(53.12, 1.0, tone('sine', 1760, .07, .005, .7, .3));
  // ---- certification
  add(56.9, .2, tone('triangle', 1400, .035, .002, .08)); add(57.3, .2, tone('triangle', 1500, .035, .002, .08));
  { const r = rng(14); for (let i = 0; i < 30; i++) add(65.6 + r() * 5.5, .1, tone('sine', 2400 + r() * 2600, .016, .003, .06, .5)); }   // carbon grains glinting
  add(65.4, 6.4, o => { const n = A.N(AU.pink, true), bp = A.F('bandpass', 900, .7), g2 = A.G(); A.chain(n, bp, g2, out(o)); A.sus(g2, o.at, o.end, .03, .8, 1.2); play(o, n, o.at, o.end); }, true);
  add(73.6, 1.3, tone('sine', 820, .03, .1, 1.15, .2, 260));                            // credit column descends
  add(74.4, .9, tone('sine', 92, .45, .004, .7, .6, 36));                                // Grade 1: deep thud with tail
  add(74.4, .4, noiseHit('lowpass', 260, .7, .22, .002, .3, 90, .5));
  add(74.52, 1.9, o => { const lp = A.F('lowpass', 400, 1.1), g2 = A.G(); A.chain(lp, g2, out(o)); const sg = A.G(.4); g2.connect(sg); sg.connect(send(o));
    lp.frequency.setValueAtTime(400, o.at); lp.frequency.exponentialRampToValueAtTime(3400, o.at + .25); lp.frequency.exponentialRampToValueAtTime(1600, o.end);
    A.sus(g2, o.at, o.end, 1, .03, 1.0);
    [60, 64, 67, 72, 48].forEach(m => [-8, 8].forEach(dt => { const os = A.O('sawtooth', mtof(m)); os.detune.value = dt; const og = A.G(.02); A.chain(os, og, lp); play(o, os, o.at, o.end); }));
  });
  { const r = rng(66); for (let i = 0; i < 18; i++) add(74.6 + r() * 3, .08, tone('sine', 2600 + r() * 2600, .015, .003, .06, .5)); }
  // ---- closing: warm swell under the worker, final chord under the end card
  add(81, 6.2, o => { const lp = A.F('lowpass', 900, .6), g2 = A.G(); A.chain(lp, g2, out(o)); const sg = A.G(.35); g2.connect(sg); sg.connect(send(o));
    lp.frequency.setValueAtTime(900, o.at); lp.frequency.linearRampToValueAtTime(2600, o.end); A.sus(g2, o.at, o.end, 1, 1.5, 1.5);
    [48, 55, 60, 64, 67].forEach(m => { const os = A.O('triangle', mtof(m)), og = A.G(.016); A.chain(os, og, lp); play(o, os, o.at, o.end); }); }, true);
  add(87, 4, o => { const lp = A.F('lowpass', 1400, .6), g2 = A.G(); A.chain(lp, g2, out(o)); const sg = A.G(.5); g2.connect(sg); sg.connect(send(o));
    A.sus(g2, o.at, o.end, 1, .6, 1.4);
    [36, 48, 55, 60, 64, 72].forEach(m => [['sine', 0], ['triangle', 6]].forEach(([ty, c]) => { const os = A.O(ty, mtof(m)); os.detune.value = c; const og = A.G(.014); A.chain(os, og, lp); play(o, os, o.at, o.end); })); }, true);
  add(87.1, 1.4, tone('sine', 1046.5, .04, .01, 1.3, .6));
  ev.sort((a, b) => a.t - b.t);
}
