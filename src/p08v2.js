
/* ============================================================
   PLATE 08 v2 — certification, POSCO Studio science-scene grammar:
   one hero object per shot, soft studio light, shallow depth of field, minimal labels
   ============================================================ */
const SK = { ink:'#2A2622', soft:'#7E7368', tq:'#1BA39C', red:'#B5473A', green:'#2E8A5E', heat:'#C2672A' };
function T(s, x, y, size, w = 500, col = SK.ink, align = 'left') { g.font = font(w, size); g.fillStyle = col; g.textAlign = align; g.textBaseline = 'alphabetic'; g.fillText(s, x, y); }
function leader(x0, y0, x1, y1, col = 'rgba(42,38,34,.55)') { g.save(); g.strokeStyle = col; g.lineWidth = 1; g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.lineTo(x1 + (x1 > x0 ? 22 : -22), y1); g.stroke(); g.fillStyle = col; g.beginPath(); g.arc(x0, y0, 2.6, 0, 7); g.fill(); g.restore(); }
function capDark(title, sub) { T('| ' + title + ' |', W - 120, H - 132, 40, 500, SK.ink, 'right'); if (sub) T(sub, W - 128, H - 88, 28, 500, SK.soft, 'right'); }
function mkc() { const c = document.createElement('canvas'); c.width = W * DPR; c.height = H * DPR; const q = c.getContext('2d'); q.setTransform(DPR, 0, 0, DPR, 0, 0); return [c, q]; }
function cove() {                                               // seamless studio backdrop
  let q = g.createLinearGradient(0, 0, 0, H); q.addColorStop(0, '#D8CFC3'); q.addColorStop(.42, '#EDE7DE'); q.addColorStop(.58, '#E9E2D8'); q.addColorStop(1, '#CFC5B8');
  g.fillStyle = q; g.fillRect(0, 0, W, H);
  q = g.createRadialGradient(W * .42, H * .38, 60, W * .5, H * .5, W * .8); q.addColorStop(0, 'rgba(255,250,240,.65)'); q.addColorStop(.5, 'rgba(255,250,240,0)'); q.addColorStop(1, 'rgba(90,70,50,.22)');
  g.fillStyle = q; g.fillRect(0, 0, W, H);
}
function grainPass(a = .07) { const r = rng(9), d = g.createImageData(256, 256); for (let i = 0; i < d.data.length; i += 4) { const v = 128 + (r() - .5) * 100; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
  const c = document.createElement('canvas'); c.width = c.height = 256; c.getContext('2d').putImageData(d, 0, 0);
  g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'overlay'; g.globalAlpha = a; g.fillStyle = g.createPattern(c, 'repeat'); g.fillRect(0, 0, W * DPR, H * DPR); g.restore(); }
function vignette() { const q = g.createRadialGradient(W / 2, H * .5, H * .45, W / 2, H * .5, H * 1.05); q.addColorStop(0, 'rgba(0,0,0,0)'); q.addColorStop(1, 'rgba(60,45,30,.35)'); g.fillStyle = q; g.fillRect(0, 0, W, H); }

/* ---------- 3D columns ---------- */
const UNIT = 5;                                                 // metres per kgCO2e
const COLS = { w:3.2, d:3.2, gap:5.4 };
const colX = i => i * COLS.gap;
function faceGrad(pts, c0, c1) { const ys = pts.map(p => p[1]); return g.createLinearGradient(0, Math.max(...ys), 0, Math.min(...ys)); }
function column(i, v0, v1, base, opt = {}) {
  const x = colX(i), y = 0, z0 = Math.min(v0, v1) * UNIT, z1 = Math.max(v0, v1) * UNIT, w = COLS.w, d = COLS.d;
  const F = (pts, stops) => { const sp = projPoly(pts); if (sp.length < 3) return; path(sp); const ys = sp.map(p => p[1]), xs = sp.map(p => p[0]);
    const q = opt.horiz ? g.createLinearGradient(Math.min(...xs), 0, Math.max(...xs), 0) : g.createLinearGradient(0, Math.max(...ys), 0, Math.min(...ys)); stops.forEach(([o, c]) => q.addColorStop(o, c)); g.fillStyle = q; g.fill(); };
  const a = opt.alpha ?? 1;
  g.save(); g.globalAlpha = a;
  F([[x, y + d, z0], [x + w, y + d, z0], [x + w, y + d, z1], [x, y + d, z1]], [[0, shade(base, -.38)], [.55, shade(base, -.12)], [1, shade(base, .05)]]);          // front-left face
  F([[x + w, y, z0], [x + w, y + d, z0], [x + w, y + d, z1], [x + w, y, z1]], [[0, shade(base, -.15)], [.6, shade(base, .18)], [1, shade(base, .32)]]);            // lit face
  F([[x, y, z1], [x + w, y, z1], [x + w, y + d, z1], [x, y + d, z1]], [[0, shade(base, .45)], [1, shade(base, .62)]]);                                             // top
  // specular edge highlight on the lit vertical edge
  const e0 = P(x + w, y + d, z0), e1 = P(x + w, y + d, z1); g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 1.4; g.beginPath(); g.moveTo(e0[0], e0[1]); g.lineTo(e1[0], e1[1]); g.stroke();
  const t0 = P(x, y + d, z1), t1 = P(x + w, y + d, z1), t2 = P(x + w, y, z1); g.strokeStyle = 'rgba(255,255,255,.7)'; g.lineWidth = 1; g.beginPath(); g.moveTo(t0[0], t0[1]); g.lineTo(t1[0], t1[1]); g.lineTo(t2[0], t2[1]); g.stroke();
  g.restore();
}
function floorAndReflect(cols, under) {
  // under-floor part (seen through the glass floor), then the floor, then mirror reflections
  if (under) under();
  const fl = projPoly([[-2000, -2000, 0], [2000, -2000, 0], [2000, 2000, 0], [-2000, 2000, 0]]);
  path(fl); const ys = fl.map(p => p[1]); let q = g.createLinearGradient(0, Math.min(...ys), 0, H); q.addColorStop(0, 'rgba(232,225,215,.0)'); q.addColorStop(.3, under ? 'rgba(226,219,209,.80)' : 'rgba(226,219,209,.95)'); q.addColorStop(1, under ? 'rgba(205,196,184,.86)' : 'rgba(200,190,178,1)'); g.fillStyle = q; g.fill();
  // reflections (mirror in z), blurred and faded
  const [rc, rg] = mkc(); const keep = g; g = rg; cols.forEach(c => { if (c[2] > 0) column(c[0], -c[1], -c[2], c[3]); }); g = keep;
  g.save(); g.globalAlpha = .16; g.filter = 'blur(6px)'; g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(rc, 0, 0); g.restore();
  // contact shadows
  cols.forEach(([i]) => { const c = P(colX(i) + COLS.w / 2 - 1.2, COLS.d / 2 + 1.4, 0), k = S(colX(i), 1.6, 0);
    g.save(); g.filter = 'blur(14px)'; g.fillStyle = 'rgba(70,55,40,.32)'; g.beginPath(); g.ellipse(c[0], c[1], 3 * k, 1.1 * k, -.25, 0, 7); g.fill(); g.restore(); });
}
function levelLine(v, col, label, num, side = 'right') {
  const z = v * UNIT, x0 = -4, x1 = colX(3) + COLS.w + 4, y = COLS.d + .2;
  const a = P(x0, y, z), b = P(x1, y, z);
  g.save(); g.setLineDash([12, 9]); g.strokeStyle = col; g.lineWidth = 1.6; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); g.restore();
  const e = side === 'right' ? b : a, al = side === 'right' ? 'left' : 'right', dx = side === 'right' ? 18 : -18;
  T(label, e[0] + dx, e[1] - 10, 24, 500, col, al); T(num, e[0] + dx, e[1] + 24, 30, 600, col, al);
}
function colLabel(i, v, text, dy = -30, size = 30, col = SK.ink) { const p = P(colX(i) + COLS.w / 2, COLS.d / 2, v * UNIT); T(text, p[0], p[1] + dy, size, 600, col, 'center'); }
function colName(i, text, col = SK.soft) { const p = P(colX(i) + COLS.w / 2, COLS.d + 1.4, 0); T(text, p[0], p[1] + 46, 24, 500, col, 'center'); }

function shotColumns(stage) {
  const cq = (new URLSearchParams(location.search).get('cam') || '').split(',').map(Number);
  const cam = cq.length === 7 ? cq : (stage === 'A' ? [62, 66, 24, 8.5, 1, 9.5, 34] : [100, 106, 22, 9.5, 1, -4.5, 40]);
  setCam([cam[0], cam[1], cam[2]], [cam[3], cam[4], cam[5]], cam[6]);
  cove();
  const NAVY = '#2E4C70', STEEL = '#7D93AD', TQ = '#1BA39C';
  const cols = [[0, 0, 3.177, STEEL], [1, 3.177, 3.238, STEEL], [2, 0, 3.238, NAVY]];
  const under = stage === 'C' ? () => { column(3, -4.762, 0, '#1E9C95');
      const p = P(colX(3) + COLS.w / 2, COLS.d / 2, -4.762 * UNIT); g.save(); g.globalCompositeOperation = 'lighter'; const q = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], 160); q.addColorStop(0, 'rgba(60,200,190,.35)'); q.addColorStop(1, 'rgba(60,200,190,0)'); g.fillStyle = q; g.fillRect(p[0] - 160, p[1] - 160, 320, 320); g.restore(); } : null;
  floorAndReflect(cols, null);
  if (under) { g.save(); g.globalAlpha = .62; under(); g.restore();
    const rim = projPoly([[colX(3) - .3, -.3, .01], [colX(3) + COLS.w + .3, -.3, .01], [colX(3) + COLS.w + .3, COLS.d + .3, .01], [colX(3) - .3, COLS.d + .3, .01]]); path(rim); g.strokeStyle = 'rgba(27,163,156,.9)'; g.lineWidth = 1.4; g.stroke(); }
  levelLine(4.0, SK.red, '청정수소 기준', '4.0');
  levelLine(0.1, SK.green, '1등급 기준', '0.1', 'left');
  cols.forEach(c => column(c[0], c[1], c[2], c[3]));
  if (stage === 'C') { column(3, 0, 3.238, TQ, { alpha:.82 });
    const p = P(colX(3) + COLS.w / 2, 0, 3.238 * UNIT); }
  if (stage === 'A') { colLabel(0, 3.177, '3.177'); colLabel(1, 3.238, '+0.061', -30, 26, SK.soft); colLabel(2, 3.238, '3.238'); ['원료 가스', '물·탈루', '소계'].forEach((t, i) => colName(i, t)); }
  else { colLabel(2, 3.238, '3.238', -30, 28); }
  if (stage === 'A') { const p = P(colX(2) + COLS.w + .2, COLS.d, 2.3 * UNIT); leader(p[0], p[1], p[0] + 70, p[1] - 40, 'rgba(194,103,42,.8)'); T('4등급', p[0] + 100, p[1] - 30, 32, 600, SK.heat); }
  if (stage === 'C') {
    const m = P(colX(3) + COLS.w / 2, COLS.d / 2 + 1.7, 1.4 * UNIT); T('−8.0', m[0], m[1], 34, 600, '#FFFFFF', 'center');
    const b = P(colX(3) + COLS.w / 2, COLS.d / 2, -4.762 * UNIT), k = S(colX(3), 1, -4.762 * UNIT);
    // translucent halo (after the reference's hydrogen-reduction shot)
    g.save(); const R0 = 9 * k; let q = g.createRadialGradient(b[0], b[1], R0 * .55, b[0], b[1], R0); q.addColorStop(0, 'rgba(27,163,156,0)'); q.addColorStop(.82, 'rgba(27,163,156,.10)'); q.addColorStop(.95, 'rgba(255,255,255,.55)'); q.addColorStop(1, 'rgba(27,163,156,0)');
    g.fillStyle = q; g.beginPath(); g.ellipse(b[0], b[1], R0, R0 * .42, 0, 0, 7); g.fill(); g.strokeStyle = 'rgba(255,255,255,.75)'; g.lineWidth = 1.2; g.beginPath(); g.ellipse(b[0], b[1], R0 * .97, R0 * .41, 0, 0, 7); g.stroke(); g.restore();
    leader(b[0] - R0 * .97, b[1], b[0] - R0 - 60, b[1] - 50, 'rgba(27,163,156,.9)'); T('−4.762', b[0] - R0 - 92, b[1] - 40, 36, 600, SK.tq, 'right');
    const cn = P(colX(3) + COLS.w + .3, COLS.d / 2, 1.2 * UNIT); leader(cn[0], cn[1], cn[0] + 60, cn[1] - 30, 'rgba(27,163,156,.9)'); T('고체탄소 크레딧', cn[0] + 92, cn[1] - 20, 28, 500, SK.tq);
  }
  vignette(); grainPass();
  if (stage === 'A') capDark('수소 1kg의 탄소 영수증', '재생·원전 전력 → 전기 배출 0');
  else capDark('청정수소 1등급', 'KEEI 산정 −4.762 kgCO₂e/kgH₂');
}

/* ---------- 08B: solid carbon close-up ---------- */
function granule(x, y, r, rr, light) {
  const n = 6 + Math.floor(rr() * 3); g.beginPath();
  for (let k = 0; k < n; k++) { const a = k / n * 6.283, rad = r * (.72 + rr() * .45); g.lineTo(x + Math.cos(a) * rad, y + Math.sin(a) * rad * .85); }
  g.closePath(); const q = g.createRadialGradient(x - r * .35, y - r * .4, r * .1, x, y, r * 1.2);
  const L = 18 + light * 40; q.addColorStop(0, `rgb(${L + 34},${L + 32},${L + 34})`); q.addColorStop(.5, `rgb(${L},${L - 1},${L})`); q.addColorStop(1, '#0A0A0C'); g.fillStyle = q; g.fill();
  if (rr() > .55) { g.fillStyle = `rgba(255,255,255,${.12 + light * .25})`; g.beginPath(); g.arc(x - r * .3, y - r * .35, r * .22, 0, 7); g.fill(); }
}
function shotCarbon() {
  cove();
  const r = rng(77), crest = x => 450 + 760 * (1 - Math.exp(-Math.pow((x - 700) / 440, 2)));    // screen y of the heap surface
  g.save(); g.filter = 'blur(34px)'; g.fillStyle = 'rgba(60,45,30,.38)'; g.beginPath(); g.ellipse(760, 1010, 720, 110, 0, 0, 7); g.fill(); g.restore();
  // body: dark fill, then layers of granules from the back (blurred) to the front (sharp)
  g.beginPath(); g.moveTo(0, H); for (let x = 0; x <= W; x += 10) g.lineTo(x, crest(x) + 18); g.lineTo(W, H); g.closePath(); g.fillStyle = '#121214'; g.fill();
  const [bc, bg] = mkc(); const keep = g; g = bg;
  for (let i = 0; i < 2200; i++) { const x = r() * W, y = crest(x) - 6 + r() * 24; if (y > H + 20) continue; granule(x, y, 5 + r() * 6, r, .25 + r() * .3); }
  g = keep; g.save(); g.filter = 'blur(4px)'; g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(bc, 0, 0); g.restore();
  for (let i = 0; i < 9000; i++) {
    const x = r() * W, y0 = crest(x), y = y0 + 10 + Math.pow(r(), 1.3) * (H + 40 - y0); if (y > H + 30) continue;
    const depth = (y - y0) / 300, light = Math.max(0, 1 - depth) * (.55 + .45 * Math.exp(-Math.pow((x - 560) / 380, 2)));
    granule(x, y, 7 + r() * 9 + Math.min(14, depth * 8), r, light);
  }
  // grains lifting off the crest, drifting up-right into the light
  for (let i = 0; i < 320; i++) { const t = Math.pow(r(), .7), x = 640 + t * 760 + (r() - .5) * 160, y = crest(640) - 30 - t * 330 + (r() - .5) * 140; granule(x, y, 1.6 + r() * 4.2 * (1 - t * .5), r, .45); }
  // out-of-focus foreground and background grains (depth of field)
  const [fc, fg] = mkc(); g = fg;
  for (let i = 0; i < 16; i++) granule(r() * 1200, 880 + r() * 260, 30 + r() * 46, r, .12);
  for (let i = 0; i < 16; i++) granule(1050 + r() * 870, 60 + r() * 360, 8 + r() * 18, r, .35);
  g = keep; g.save(); g.filter = 'blur(18px)'; g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(fc, 0, 0); g.restore();
  vignette(); grainPass();
  leader(980, 600, 1210, 430); T('고체탄소 3.2kg', 1244, 440, 38, 600);
  ['콘크리트 혼화재', '복합소재', '전극재'].forEach((u, i) => T(u, 1244, 500 + i * 42, 28, 500, SK.soft));
  T('추적 증빙 ✓', 1244, 500 + 3 * 42 + 20, 28, 600, SK.tq);
  capDark('판매하고, 다시 태워지지 않게 고정', '크레딧 3.2 × 2.5 = 8.0 인정');
}
const cv = document.getElementById('cv');
function render() {
  DPR = Math.max(1, window.devicePixelRatio || 1); const sc = Math.min(innerWidth / W, innerHeight / H);
  cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
  cv.style.width = W * sc + 'px'; cv.style.height = H * sc + 'px'; cv.style.left = (innerWidth - W * sc) / 2 + 'px'; cv.style.top = (innerHeight - H * sc) / 2 + 'px';
  g = cv.getContext('2d'); g.setTransform(DPR, 0, 0, DPR, 0, 0);
  if (STAGE === 'B') shotCarbon(); else shotColumns(STAGE);
  window.__ready = true;
}
addEventListener('resize', render);
FONT_READY.then(render);
</script>
</body>
</html>
