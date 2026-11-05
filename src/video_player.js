
/* ============================================================
   VIDEO — 80 s film assembled from the code-drawn scenes
   Scenes are rendered once at load (base layer + HUD layer), then the master
   timeline animates camera push, transitions, HUD reveal, captions, live FX and sound.
   ============================================================ */
const DUR = 80.0, XF = .6, RQ = 1.1;                       // total length, crossfade, prerender scale (push-in headroom)
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, k) => a + (b - a) * k;
const ease = k => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
const prog = (t, a, b) => clamp((t - a) / (b - a));
function win(t, a, b, fi = .5, fo = .4) { if (t < a || t > b) return 0; return Math.min(ease(prog(t, a, a + fi)), 1 - ease(prog(t, b - fo, b))); }

const NT0 = NO_TREES.length, TREE0 = tree, CAP0 = caption;
function resetScene() { SHOT = setupShot; EXTRA_GROUND = null; EXTRA_WORLD = null; POST = null; NO_TREES.length = NT0; tree = TREE0; window.SUNXY = undefined; HOLO = false; caption = CAP0; }

// ---- prerender helpers
function renderBase(postMode) {
  const w = Math.round(W * RQ), h = Math.round(H * RQ);
  SHOT(); const hy = horizonY();
  const B = mk(w, h); DPR = RQ; g = B.getContext('2d'); g.setTransform(RQ, 0, 0, RQ, 0, 0);
  sky(g, hy);
  g.fillStyle = lg(0, Math.max(0, hy), 0, H, [[0, '#9DB596'], [.25, '#7E9F6B'], [1, '#6A8F57']]); g.fillRect(0, Math.max(0, hy), W, H - Math.max(0, hy));
  SEA_TOP = -9000; drawSea(); drawGroundPlan(); if (EXTRA_GROUND) EXTRA_GROUND(); drawForest(); solarField(); drawShadows(); drawSolar();
  OBJ.slice().sort((a, b) => a.depth - b.depth).forEach(o => o.f());
  if (EXTRA_WORLD) EXTRA_WORLD();
  const out = mk(w, h), gm = out.getContext('2d');
  gm.filter = 'contrast(1.12) saturate(.92)'; gm.drawImage(B, 0, 0); gm.filter = 'none';
  gm.setTransform(RQ, 0, 0, RQ, 0, 0); grade(gm, hy);
  caption = () => {};
  let ov = null;
  if (POST && postMode === 'base') POST(gm);
  if (POST && postMode === 'overlay') { ov = mk(w, h); const og = ov.getContext('2d'); og.setTransform(RQ, 0, 0, RQ, 0, 0); POST(og); }
  caption = CAP0;
  return { base: out, ov };
}
function renderHolo() {
  const w = Math.round(W * RQ), h = Math.round(H * RQ), dpr = RQ;
  setupShot(); const hy = horizonY(); DPR = dpr;
  const Ev = mk(w, h); g = Ev.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = lg(0, hy, 0, H, [[0, '#9DB596'], [.25, '#7E9F6B'], [1, '#6A8F57']]); g.fillRect(0, hy, W, H - hy);
  SEA_TOP = -9000; HOLO = false; drawSea(); drawGroundPlan(); drawForest(); solarField(); drawShadows(); drawSolar();
  OBJ.filter(o => o.kind === 'env').sort((a, b) => a.depth - b.depth).forEach(o => o.f());
  const Hc = mk(w, h); g = Hc.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  HOLO = false; poly3([[0, 0], [205, 0], [205, 145], [0, 145]], null, 'rgba(150,226,255,.8)', 1.2); HOLO = true;
  for (let x = 0; x <= 205; x += 15) { HOLO = false; line3([x, 0, 0], [x, 145, 0], 'rgba(120,200,255,.16)', .5); HOLO = true; }
  for (let y = 0; y <= 145; y += 15) { HOLO = false; line3([0, y, 0], [205, y, 0], 'rgba(120,200,255,.16)', .5); HOLO = true; }
  OBJ.filter(o => o.kind === 'plant').sort((a, b) => a.depth - b.depth).forEach(o => o.f());
  HOLO = false;
  const out = mk(w, h), gm = out.getContext('2d'); gm.setTransform(dpr, 0, 0, dpr, 0, 0); duskSky(gm, hy);
  gm.setTransform(1, 0, 0, 1, 0, 0);
  gm.filter = 'brightness(.5) saturate(.75) contrast(1.1)'; gm.drawImage(Ev, 0, 0); gm.filter = 'none';
  gm.save(); gm.globalCompositeOperation = 'soft-light'; gm.fillStyle = 'rgba(40,80,140,.7)'; gm.fillRect(0, 0, w, h); gm.restore();
  gm.setTransform(dpr, 0, 0, dpr, 0, 0); lights(gm); gm.setTransform(1, 0, 0, 1, 0, 0);
  gm.save(); gm.globalCompositeOperation = 'lighter';
  gm.filter = `blur(${14 * dpr}px)`; gm.globalAlpha = .5; gm.drawImage(Hc, 0, 0);
  gm.filter = `blur(${4 * dpr}px)`; gm.globalAlpha = .55; gm.drawImage(Hc, 0, 0);
  gm.filter = 'none'; gm.globalAlpha = 1; gm.drawImage(Hc, 0, 0); gm.restore();
  gm.setTransform(dpr, 0, 0, dpr, 0, 0);
  h2Badge(gm, 172, 54, 25, 40); h2Badge(gm, 188, 64, 22, 34);
  let q = gm.createLinearGradient(0, hy - 60, 0, hy + 120); q.addColorStop(0, 'rgba(255,170,110,0)'); q.addColorStop(.35, 'rgba(255,170,110,.22)'); q.addColorStop(1, 'rgba(255,170,110,0)');
  gm.fillStyle = q; gm.fillRect(0, hy - 60, W, 180);
  q = gm.createRadialGradient(W / 2, H * .52, H * .38, W / 2, H * .52, H * 1.0); q.addColorStop(0, 'rgba(0,0,0,0)'); q.addColorStop(1, 'rgba(2,6,14,.7)');
  gm.fillStyle = q; gm.fillRect(0, 0, W, H);
  gm.save(); gm.globalCompositeOperation = 'overlay'; gm.globalAlpha = .1; gm.fillStyle = gm.createPattern(grain, 'repeat'); gm.fillRect(0, 0, W, H); gm.restore();
  return { base: out, ov: null };
}
function renderStudio(fn, arg) {
  const w = Math.round(W * RQ), h = Math.round(H * RQ), c = mk(w, h);
  DPR = RQ; g = c.getContext('2d'); g.setTransform(RQ, 0, 0, RQ, 0, 0); fn(arg);
  return { base: c, ov: null };
}
// close-up of the worker over a softened scene (used for the inspection insert)
function heroOver(src, sunXY) {
  const w = src.width, h = src.height, c = mk(w, h), gm = c.getContext('2d');
  gm.filter = `blur(${5 * RQ}px)`; gm.drawImage(src, 0, 0); gm.filter = 'none';
  gm.setTransform(RQ, 0, 0, RQ, 0, 0);
  gm.save(); gm.globalCompositeOperation = 'screen'; let q = gm.createRadialGradient(sunXY[0], sunXY[1], 10, sunXY[0], sunXY[1], 1100); q.addColorStop(0, 'rgba(255,214,150,.45)'); q.addColorStop(.35, 'rgba(255,200,130,.12)'); q.addColorStop(1, 'rgba(255,200,130,0)'); gm.fillStyle = q; gm.fillRect(0, 0, W, H); gm.restore();
  const keep = g; g = gm; DPR = RQ; heroWorker(1360, 470, 430); g = keep;
  q = gm.createRadialGradient(W * .45, H * .5, H * .45, W * .45, H * .5, H * 1.05); q.addColorStop(0, 'rgba(0,0,0,0)'); q.addColorStop(1, 'rgba(6,12,22,.55)'); gm.fillStyle = q; gm.fillRect(0, 0, W, H);
  gm.save(); gm.globalCompositeOperation = 'overlay'; gm.globalAlpha = .08; gm.fillStyle = gm.createPattern(grain, 'repeat'); gm.fillRect(0, 0, W, H); gm.restore();
  return { base: c, ov: null };
}

// ---- shot list (times in seconds)
const SH = [
  { id:'open', t0:0,    t1:14,   z:[1.0, 1.09], f:[[960, 600], [1000, 560]] },
  { id:'p02w', t0:14,   t1:17,   z:[1.0, 1.04], f:[[1250, 460], [1230, 450]] },
  { id:'p02',  t0:17,   t1:21.5, z:[1.0, 1.06], f:[[700, 520], [720, 520]] },
  { id:'p03',  t0:21.5, t1:29,   z:[1.0, 1.07], f:[[800, 540], [820, 520]] },
  { id:'p04',  t0:29,   t1:36,   z:[1.0, 1.07], f:[[760, 540], [780, 530]] },
  { id:'p05',  t0:36,   t1:43,   z:[1.0, 1.07], f:[[1100, 560], [1080, 540]] },
  { id:'p06',  t0:43,   t1:50,   z:[1.0, 1.07], f:[[860, 520], [900, 480]] },
  { id:'p07',  t0:50,   t1:56,   z:[1.0, 1.05], f:[[960, 520], [960, 500]] },
  { id:'p08a', t0:56,   t1:60.8, z:[1.0, 1.05], f:[[760, 520], [760, 500]] },
  { id:'p08b', t0:60.8, t1:65.4, z:[1.0, 1.06], f:[[760, 560], [820, 520]] },
  { id:'p08c', t0:65.4, t1:70.5, z:[1.0, 1.05], f:[[1000, 500], [1000, 560]] },
  { id:'p09',  t0:70.5, t1:76.5, z:[1.0, 1.04], f:[[1250, 450], [1250, 430]] },
  { id:'end',  t0:76.5, t1:80 }
];
const CAPS = [
  [0.9, 5.0, '2030 · POSCO 청록수소 플랜트', '메탄을 수소와 고체탄소로 — CO₂ 굴뚝이 없는 수소 공장'],
  [8.0, 13.7, '2030 · POSCO 청록수소 플랜트', '햇살 좋은 날, 수소 안전을 하나씩 점검합니다'],
  [14.5, 21.3, '① 원료 인입·전처리', ''], [22.1, 28.8, '② 열분해 반응기', ''], [29.6, 35.8, '③ 탄소 분리·저장', ''],
  [36.6, 42.8, '④ 수소 정제·압축·저장', ''], [43.6, 49.8, '⑤ 배관 이송', ''], [50.6, 55.8, '착공 전 관문을 모두 통과 — 안전하게 짓는다', '']
];
const IMG = {}, FX = {};
const LOADERS = [
  ['open-holo', () => { resetScene(); IMG.holo = renderHolo(); }],
  ['open-day', () => { resetScene(); IMG.open = renderBase('none'); }],
  ['p02', () => { resetScene(); SETUP.p02(); IMG.p02 = renderBase('overlay'); FX.p02 = { alarm: P(19.5, 114.41, 2.85) }; }],
  ['p02w', () => { resetScene(); SETUP.p02(); POST = null; const b = renderBase('none'); IMG.p02w = heroOver(b.base, [1610, 92]); }],
  ['p03', () => { resetScene(); SETUP.p03(); IMG.p03 = renderBase('overlay');
    FX.p03 = { glow: REACT.flatMap(([cx, cy]) => { const [fx, fy] = facing(cx, cy, 2.75); return [7.2, 10.6].map(z => [...P(fx, fy, z), S(fx, fy, z)]); }) }; }],
  ['p04', () => { resetScene(); SETUP.p04(); IMG.p04 = renderBase('overlay'); FX.p04 = { dust: P(136.5, 82, 7.4), hood: P(136.5, 82, 9.2), k: S(136.5, 82, 7) }; }],
  ['p05', () => { resetScene(); SETUP.p05(); IMG.p05 = renderBase('overlay'); FX.p05 = { lamps: UVIR.map(([x, y, hh]) => P(x, y + .26, hh + .22)), leak: P(166, 82.5, 2.4) }; }],
  ['p06', () => { resetScene(); SETUP.p06(); IMG.p06 = renderBase('overlay');
    FX.p06 = { lamps: DETECT.map(([x, y]) => P(x + .22, y, 6.5)), main: [P(197.6, 50, 8.1), P(197.6, -30, 8.1)] }; }],
  ['p07', () => { resetScene(); SETUP.p07(); IMG.p07 = renderBase('overlay'); }],
  ['p08a', () => { IMG.p08a = renderStudio(shotColumns, 'A'); }],
  ['p08b', () => { IMG.p08b = renderStudio(shotCarbon); }],
  ['p08c', () => { IMG.p08c = renderStudio(shotColumns, 'C'); }],
  ['p09', () => { resetScene(); SETUP.p09(); IMG.p09 = renderBase('base'); }]
];

// ---- per-frame drawing
const cvx = cv.getContext('2d');
function kb(s, t) {                                   // camera push: zoom z about a drifting focus point F
  const u = ease(prog(t, s.t0, s.t1 + XF)), z = lerp(s.z[0], s.z[1], u);
  return { z, F: [lerp(s.f[0][0], s.f[1][0], u), lerp(s.f[0][1], s.f[1][1], u)] };
}
function drawImg(img, k) { g.save(); g.translate(k.F[0] * (1 - k.z), k.F[1] * (1 - k.z)); g.scale(k.z / RQ, k.z / RQ); g.drawImage(img, 0, 0); g.restore(); }
function stageXf(k) { g.translate(k.F[0] * (1 - k.z), k.F[1] * (1 - k.z)); g.scale(k.z, k.z); }
function drawShot(s, t) {
  if (s.id === 'end') return drawEnd(t);
  const k = kb(s, t);
  if (s.id === 'open') {
    drawImg(IMG.holo.base, k);
    const sx = lerp(-400, W + 400, ease(prog(t, 4.8, 7.8)));      // scan line sweeping left -> right reveals the real plant
    if (t > 4.8) {
      g.save(); g.beginPath(); g.moveTo(-10, -10); g.lineTo(sx + 180, -10); g.lineTo(sx - 180, H + 10); g.lineTo(-10, H + 10); g.closePath(); g.clip(); drawImg(IMG.open.base, k); g.restore();
      if (t < 8.1) { const a = 1 - prog(t, 7.4, 8.1);
        g.save(); g.globalCompositeOperation = 'lighter'; g.globalAlpha = a;
        g.strokeStyle = 'rgba(150,230,255,.55)'; g.lineWidth = 26; g.filter = 'blur(14px)'; g.beginPath(); g.moveTo(sx + 180, 0); g.lineTo(sx - 180, H); g.stroke(); g.filter = 'none';
        g.strokeStyle = 'rgba(225,250,255,.95)'; g.lineWidth = 3; g.beginPath(); g.moveTo(sx + 180, 0); g.lineTo(sx - 180, H); g.stroke(); g.restore(); }
    }
    return;
  }
  const im = IMG[s.id]; drawImg(im.base, k);
  liveFX(s, t, k);
  if (im.ov) {
    const r0 = s.t0 + 1.0, a = win(t, r0, s.t1 + XF, .5, .45), wipe = ease(prog(t, r0, r0 + .9));
    if (a > 0) { g.save(); g.globalAlpha = a; g.beginPath(); g.rect(0, 0, W * wipe + 60, H); g.clip(); drawImg(im.ov, k); g.restore(); }
  }
  if (s.id === 'p09') drawP09Title(t);
}
function liveFX(s, t, k) {
  const fx = FX[s.id]; if (!fx) return;
  g.save(); stageXf(k);
  if (s.id === 'p02' && t > s.t0 + 1.2) { const on = Math.sin(t * 9) > 0 ? .9 : .25; const [x, y] = fx.alarm;
    g.globalCompositeOperation = 'lighter'; const q = g.createRadialGradient(x, y, 0, x, y, 26); q.addColorStop(0, `rgba(255,90,70,${on})`); q.addColorStop(1, 'rgba(255,90,70,0)'); g.fillStyle = q; g.beginPath(); g.arc(x, y, 26, 0, 7); g.fill(); }
  if (s.id === 'p03') { g.globalCompositeOperation = 'lighter'; fx.glow.forEach(([x, y, kk], i) => { const a = .18 + .14 * Math.sin(t * 3.1 + i * 1.7), R = 3.6 * kk;
    const q = g.createRadialGradient(x, y, 0, x, y, R); q.addColorStop(0, `rgba(255,170,80,${a})`); q.addColorStop(1, 'rgba(255,140,60,0)'); g.fillStyle = q; g.beginPath(); g.arc(x, y, R, 0, 7); g.fill(); }); }
  if (s.id === 'p04') { const r = rng(5), [dx, dy] = fx.dust, [hx, hy] = fx.hood, kk = fx.k;
    for (let i = 0; i < 90; i++) { const ph = (r() + (t - s.t0) * (.12 + r() * .1)) % 1, a0 = r() * 6.283, d0 = (2 + r() * 3) * kk;
      const x = lerp(dx + Math.cos(a0) * d0, hx, ph * ph), y = lerp(dy + Math.sin(a0) * d0 * .6, hy, ph * ph);
      g.fillStyle = `rgba(22,24,28,${.55 * (1 - ph)})`; g.beginPath(); g.arc(x, y, 1 + r() * 2, 0, 7); g.fill(); } }
  if (s.id === 'p05') { const on = Math.sin(t * 7) > 0 ? .95 : .35; g.globalCompositeOperation = 'lighter';
    fx.lamps.forEach(([x, y]) => { const q = g.createRadialGradient(x, y, 0, x, y, 18); q.addColorStop(0, `rgba(255,170,90,${on})`); q.addColorStop(1, 'rgba(255,150,70,0)'); g.fillStyle = q; g.beginPath(); g.arc(x, y, 18, 0, 7); g.fill(); });
    const [lx, ly] = fx.leak; g.strokeStyle = `rgba(235,245,255,${.25 + .15 * Math.sin(t * 5)})`; g.lineWidth = 1.2;
    for (let j = -2; j <= 2; j++) { g.beginPath(); for (let v = 0; v < 70; v += 3) { const x = lx + j * 5 + Math.sin(v * .15 + t * 6 + j) * 4; v ? g.lineTo(x, ly - v) : g.moveTo(x, ly - v); } g.stroke(); } }
  if (s.id === 'p06') { g.globalCompositeOperation = 'lighter'; const [a, b] = fx.main;
    for (let i = 0; i < 6; i++) { const u = ((t - s.t0) * .22 + i / 6) % 1, x = lerp(a[0], b[0], u), y = lerp(a[1], b[1], u), R = lerp(14, 6, u);
      const q = g.createRadialGradient(x, y, 0, x, y, R); q.addColorStop(0, 'rgba(210,255,250,.7)'); q.addColorStop(1, 'rgba(160,240,235,0)'); g.fillStyle = q; g.beginPath(); g.arc(x, y, R, 0, 7); g.fill(); }
    const on = (Math.sin(t * 4) > 0) ? .95 : .4; fx.lamps.forEach(([x, y]) => { const q = g.createRadialGradient(x, y, 0, x, y, 10); q.addColorStop(0, `rgba(120,240,170,${on})`); q.addColorStop(1, 'rgba(120,240,170,0)'); g.fillStyle = q; g.beginPath(); g.arc(x, y, 10, 0, 7); g.fill(); }); }
  g.restore();
}
function drawP09Title(t) {
  const a = win(t, 71.6, 77.1, .9, .5); if (!a) return;
  g.save(); g.globalAlpha = a; g.shadowColor = 'rgba(0,10,25,.6)'; g.shadowBlur = 14; g.fillStyle = '#FFFFFF'; g.font = font(500, 60); g.textAlign = 'left'; g.textBaseline = 'alphabetic';
  const dy = (1 - a) * 14; g.fillText('안전하게 짓고,', 150, 760 + dy); g.globalAlpha = win(t, 72.4, 77.1, .9, .5); g.fillText('청정수소 1등급으로', 150, 842 + dy); g.restore();
}
function drawEnd(t) {
  g.fillStyle = '#050608'; g.fillRect(0, 0, W, H);
  const q = g.createRadialGradient(W / 2, H * .46, 20, W / 2, H * .46, 700); q.addColorStop(0, 'rgba(27,163,156,.10)'); q.addColorStop(1, 'rgba(27,163,156,0)'); g.fillStyle = q; g.fillRect(0, 0, W, H);
  const Tx = (s, y, size, w, col, a) => { g.save(); g.globalAlpha = a; g.font = font(w, size); g.fillStyle = col; g.textAlign = 'center'; g.textBaseline = 'alphabetic'; g.fillText(s, W / 2, y); g.restore(); };
  const a1 = ease(prog(t, 77.0, 77.9)), a2 = ease(prog(t, 77.4, 78.3)), a3 = ease(prog(t, 78.0, 78.8));
  Tx('POSCO HyREX 수소환원제철에', 488, 52, 500, '#FFFFFF', a1);
  Tx('청정수소 공급', 562, 52, 500, '#FFFFFF', a2);
  g.save(); g.globalAlpha = a2; g.strokeStyle = 'rgba(27,163,156,.8)'; g.lineWidth = 1.5; g.beginPath(); g.moveTo(W / 2 - 28 * a2, 626); g.lineTo(W / 2 + 28 * a2, 626); g.stroke(); g.restore();
  Tx('개념 영상 · 1등급은 고체탄소 크레딧 인정과 무탄소 전력 조달을 전제로 한 시나리오', 960, 24, 500, 'rgba(255,255,255,.6)', a3);
  Tx('한동대학교 × POSCO 위탁연구과제', 1000, 24, 500, 'rgba(255,255,255,.6)', a3);
}
function renderFrame(t) {
  t = clamp(t, 0, DUR);
  let i = SH.findIndex(s => t >= s.t0 && t < s.t1); if (i < 0) i = SH.length - 1;
  const s = SH[i];
  g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  if (i > 0 && t < s.t0 + XF) drawShot(SH[i - 1], t);
  g.save(); g.globalAlpha = i > 0 ? ease(prog(t, s.t0, s.t0 + XF)) : 1; drawShot(s, t); g.restore();
  if (t < .8) { g.fillStyle = `rgba(0,0,0,${1 - ease(prog(t, 0, .8))})`; g.fillRect(0, 0, W, H); }
  CAPS.forEach(([a, b, title, sub]) => { const al = win(t, a, b, .5, .4); if (al > 0) { g.save(); g.globalAlpha = al; caption(g, title, sub); g.restore(); } });
}

/* ---- player ---- */
const startEl = document.getElementById('start'), playBtn = document.getElementById('play'), loadEl = document.getElementById('load'), progEl = document.getElementById('prog'), fillEl = document.getElementById('fill');
let sdpr = 1, ssc = 1, sox = 0, soy = 0, LOADED = false;
const PL = { playing:false, t:0, startT:0, startClock:0, clock:null };
function resize() {
  sdpr = window.devicePixelRatio || 1; cv.width = Math.round(innerWidth * sdpr); cv.height = Math.round(innerHeight * sdpr);
  cv.style.left = '0px'; cv.style.top = '0px'; cv.style.width = innerWidth + 'px'; cv.style.height = innerHeight + 'px';
  ssc = Math.min(innerWidth / W, innerHeight / H); sox = (innerWidth - W * ssc) / 2; soy = (innerHeight - H * ssc) / 2;
}
function cur() { return PL.playing ? Math.min(DUR, PL.startT + PL.clock() - PL.startClock) : PL.t; }
function draw(t) {
  if (!LOADED) return;
  g = cvx; DPR = sdpr * ssc;
  cvx.setTransform(sdpr, 0, 0, sdpr, 0, 0); cvx.fillStyle = '#000'; cvx.fillRect(0, 0, innerWidth, innerHeight);
  cvx.save(); cvx.translate(sox, soy); cvx.scale(ssc, ssc); cvx.beginPath(); cvx.rect(0, 0, W, H); cvx.clip();
  renderFrame(t); cvx.restore();
  fillEl.style.width = (t / DUR * 100) + '%';
}
function vPlay() { if (PL.t >= DUR) PL.t = 0; PL.clock = (AU.ac && AU.ac.state === 'running') ? () => AU.ac.currentTime : () => performance.now() / 1000; PL.startClock = PL.clock(); PL.startT = PL.t; PL.playing = true; auStart(PL.t); }
function vPause() { PL.t = cur(); PL.playing = false; auStop(); }
function vSeek(t) { const was = PL.playing; if (was) vPause(); PL.t = clamp(t, 0, DUR); if (was) vPlay(); else draw(PL.t); }
function loop() { let t = cur(); if (PL.playing && t >= DUR) { PL.t = DUR; PL.playing = false; t = DUR; setTimeout(auStop, 200); } if (PL.playing) auTick(t); draw(t); requestAnimationFrame(loop); }
setInterval(() => { if (PL.playing) auTick(cur()); }, 50);
async function begin() { if (!LOADED) return; try { auInit(); await AU.ac.resume(); } catch (e) { console.warn('audio unavailable', e); } startEl.classList.add('hide'); PL.t = 0; vPlay(); poke(); }
playBtn.addEventListener('click', begin);
addEventListener('keydown', e => {
  if (!startEl.classList.contains('hide')) { if (e.code === 'Space' || e.code === 'Enter') { e.preventDefault(); begin(); } return; }
  switch (e.code) {
    case 'Space': e.preventDefault(); PL.playing ? vPause() : vPlay(); break;
    case 'ArrowLeft': vSeek(cur() - 5); break;
    case 'ArrowRight': vSeek(cur() + 5); break;
    case 'KeyM': auMute(!AU.muted); break;
    case 'KeyR': PL.t = 0; if (!PL.playing) vPlay(); else vSeek(0); break;
    case 'KeyF': if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => {}); else document.exitFullscreen(); break;
    default: return;
  }
  poke();
});
let idleT = null;
function poke() { progEl.classList.remove('idle'); clearTimeout(idleT); idleT = setTimeout(() => progEl.classList.add('idle'), 2000); }
addEventListener('mousemove', poke);
progEl.addEventListener('click', e => { if (startEl.classList.contains('hide')) vSeek(e.clientX / innerWidth * DUR); });
addEventListener('resize', () => { resize(); draw(cur()); });
window.__seek = t => { PL.playing = false; PL.t = t; draw(t); };
resize();
FONT_READY.then(() => {
  let i = 0;
  const step = () => {
    if (i < LOADERS.length) { loadEl.textContent = `장면 준비 중 ${i + 1} / ${LOADERS.length}`; setTimeout(() => { LOADERS[i][1](); i++; step(); }, 20); return; }
    resetScene(); LOADED = true; loadEl.textContent = ''; playBtn.disabled = false;
    const qt = new URLSearchParams(location.search).get('t');
    if (qt !== null && !isNaN(parseFloat(qt))) { startEl.classList.add('hide'); progEl.classList.add('idle'); PL.t = clamp(parseFloat(qt), 0, DUR); }
    draw(PL.t); requestAnimationFrame(loop); window.__ready = true;
  };
  step();
});
</script>
</body>
</html>
