
/* ============================================================
   CINEMATIC RENDER — POSCO Studio grammar
   (drone oblique, teal/orange grade, haze, flare, grain, | caption |)
   ============================================================ */
function mk(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
const inBox = (x, y, b) => x > b[0] && x < b[2] && y > b[1] && y < b[3];
const NO_TREES = [[-16, -20, 216, 156], [221, 15, 294, 126], [94, -78, 226, -14], [207, -100, 217, 160], [-20, 145, 420, 155], [13, 150, 23, 600], [40, -16, 210, -4]];
function unproject(sx, sy) {                     // screen -> ground plane (z = 0)
  const kx = -(sx - W / 2) / CAMR.focal, ky = -(sy - H / 2) / CAMR.focal, f = CAMR.f, r = CAMR.r, u = CAMR.u;
  const dir = [f[0] + r[0] * kx + u[0] * ky, f[1] + r[1] * kx + u[1] * ky, f[2] + r[2] * kx + u[2] * ky];
  if (dir[2] >= -1e-4) return null; const t = -CAMR.p[2] / dir[2];
  return [CAMR.p[0] + dir[0] * t, CAMR.p[1] + dir[1] * t];
}
function drawForest() {
  const r = rng(91), dense = (x, y) => Math.sin(x * .061) + Math.sin(y * .053 + 1.3) + Math.sin((x - y) * .037 + 2.1) + .6 * Math.sin((x + y) * .013);
  const hy = horizonY(), seen = new Set(), trees = [];
  for (let i = 0; i < 320000; i++) {
    const sx = -60 + r() * (W + 120), sy = hy + 2 + Math.pow(r(), .7) * (H + 60 - hy);
    const q = unproject(sx, sy); if (!q) continue; const [x, y] = q;
    if (x < COAST + 6) continue;                                   // sea
    if (NO_TREES.some(b => inBox(x, y, b))) continue;
    const dn = dense(x, y); if (dn < -1.1) continue;                // open fields between forest blocks
    const key = Math.floor(x / 2.3) + ',' + Math.floor(y / 2.3); if (seen.has(key)) continue; seen.add(key);
    trees.push([x + (r() - .5) * 1.6, y + (r() - .5) * 1.6, .95 + r() * .9 + (dn > 1.2 ? .35 : 0), r()]);
  }
  trees.sort((a, b) => toCam(b[0], b[1], 0)[2] - toCam(a[0], a[1], 0)[2]);
  for (const [x, y, s, k] of trees) {
    const p = P(x, y, 0), R = s * S(x, y, 0) * .85; if (R < .6) { g.fillStyle = '#3B6440'; g.fillRect(p[0], p[1] - 1, 1.4, 1.2); continue; }
    g.fillStyle = 'rgba(12,24,20,.45)'; g.beginPath(); g.ellipse(p[0] - R * .5, p[1] + R * .1, R * 1.05, R * .5, 0, 0, 7); g.fill();
    g.fillStyle = k < .25 ? '#24492F' : k < .5 ? '#2F5636' : k < .75 ? '#3A633D' : '#4A6E3F'; g.beginPath(); g.ellipse(p[0], p[1] - R * .7, R, R * .82, 0, 0, 7); g.fill();
    g.fillStyle = k < .5 ? 'rgba(150,180,105,.30)' : 'rgba(185,200,120,.26)'; g.beginPath(); g.ellipse(p[0] + R * .28, p[1] - R * .98, R * .45, R * .36, 0, 0, 7); g.fill();
  }
}
function setupShot() {
  // drone ~32° down, looking at the plant from the land side (sea on the left, steel works behind)
  const T = [96, 18, 0], dir = nrm([.56, .83, 0]), dist = 330, hgt = 74;
  setCam([T[0] + dir[0] * dist, T[1] + dir[1] * dist, hgt], [T[0], T[1], 0], 58);
}
function sky(gg, hy) {
  let q = gg.createLinearGradient(0, 0, 0, hy); q.addColorStop(0, '#4F8CC4'); q.addColorStop(.6, '#9CC3E0'); q.addColorStop(1, '#DCE7EC');
  gg.fillStyle = q; gg.fillRect(0, 0, W, hy + 2);
  const r = rng(6);                                           // soft fair-weather cumulus near the horizon
  for (let i = 0; i < 14; i++) { const cx = r() * W, cy = hy - 30 - r() * 70, w = 60 + r() * 120;
    for (let k = 0; k < 6; k++) { const px = cx + (k - 2.5) * w * .32, py = cy - Math.sin(k / 5 * Math.PI) * w * .18, R = w * (.22 + r() * .12);
      const c = gg.createRadialGradient(px, py - R * .3, R * .1, px, py, R); c.addColorStop(0, 'rgba(255,255,255,.75)'); c.addColorStop(1, 'rgba(255,255,255,0)'); gg.fillStyle = c; gg.beginPath(); gg.arc(px, py, R, 0, 7); gg.fill(); } }
  // far shore mountains (Yeongil Bay), layered with aerial perspective
  [[hy - 26, 34, 5, '#9DB4C6', '#B9CAD6'], [hy - 12, 26, 11, '#8AA3B3', '#A9BDC9'], [hy - 2, 14, 23, '#7D9AA3', '#9DB3BA']].forEach(([y0, amp, seed, c0, c1]) => {
    const rr = rng(seed), a = rr() * 6, b = rr() * 6; gg.beginPath(); gg.moveTo(0, hy + 3);
    for (let x = 0; x <= W; x += 4) gg.lineTo(x, y0 - amp * (.5 + .3 * Math.sin(x * .0042 + a) + .14 * Math.sin(x * .013 + b) + .06 * Math.sin(x * .05 + a)));
    gg.lineTo(W, hy + 3); gg.closePath(); const lgr = gg.createLinearGradient(0, y0 - amp, 0, hy); lgr.addColorStop(0, c0); lgr.addColorStop(1, c1); gg.fillStyle = lgr; gg.fill(); });
}
const grain = (() => { const c = mk(256, 256), q = c.getContext('2d'), d = q.createImageData(256, 256), r = rng(3);
  for (let i = 0; i < d.data.length; i += 4) { const v = 128 + (r() - .5) * 120; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
  q.putImageData(d, 0, 0); return c; })();
function grade(gg, hy) {
  gg.save(); gg.globalCompositeOperation = 'soft-light';
  let q = gg.createLinearGradient(0, 0, 0, H); q.addColorStop(0, 'rgba(30,90,140,.6)'); q.addColorStop(.55, 'rgba(110,120,115,.2)'); q.addColorStop(1, 'rgba(200,130,60,.5)');
  gg.fillStyle = q; gg.fillRect(0, 0, W, H); gg.restore();
  q = gg.createLinearGradient(0, hy - 30, 0, hy + 150); q.addColorStop(0, 'rgba(214,226,234,.45)'); q.addColorStop(.4, 'rgba(214,226,234,.2)'); q.addColorStop(1, 'rgba(214,226,234,0)');
  gg.fillStyle = q; gg.fillRect(0, hy - 40, W, 210);
  const sx = (window.SUNXY || [1610, 92])[0], sy = (window.SUNXY || [1610, 92])[1];
  if (hy > 40) {
  gg.save(); gg.globalCompositeOperation = 'screen';
  q = gg.createRadialGradient(sx, sy, 3, sx, sy, 560); q.addColorStop(0, 'rgba(255,246,220,1)'); q.addColorStop(.06, 'rgba(255,232,185,.6)'); q.addColorStop(.3, 'rgba(255,214,160,.14)'); q.addColorStop(1, 'rgba(255,214,160,0)');
  gg.fillStyle = q; gg.fillRect(0, 0, W, H);
  q = gg.createLinearGradient(sx - 800, 0, sx + 800, 0); q.addColorStop(0, 'rgba(255,220,170,0)'); q.addColorStop(.5, 'rgba(255,236,205,.4)'); q.addColorStop(1, 'rgba(255,220,170,0)');
  gg.fillStyle = q; gg.fillRect(sx - 800, sy - 1.5, 1600, 3);
  [[.32, 22, .12], [.5, 54, .06], [.74, 16, .1], [1.05, 84, .05]].forEach(([k, r, al]) => { const x = sx + (W / 2 - sx) * k * 1.7, y = sy + (H / 2 - sy) * k * 1.7;
    const c = gg.createRadialGradient(x, y, 0, x, y, r); c.addColorStop(0, `rgba(170,220,255,${al})`); c.addColorStop(.7, `rgba(140,200,240,${al * .6})`); c.addColorStop(1, 'rgba(140,200,240,0)'); gg.fillStyle = c; gg.beginPath(); gg.arc(x, y, r, 0, 7); gg.fill(); });
  gg.restore();
  }
  q = gg.createRadialGradient(W / 2, H * .52, H * .38, W / 2, H * .52, H * 1.0); q.addColorStop(0, 'rgba(0,0,0,0)'); q.addColorStop(1, 'rgba(6,14,24,.6)');
  gg.fillStyle = q; gg.fillRect(0, 0, W, H);
  gg.save(); gg.globalCompositeOperation = 'overlay'; gg.globalAlpha = .09; gg.fillStyle = gg.createPattern(grain, 'repeat'); gg.fillRect(0, 0, W, H); gg.restore();
}
function caption(gg, title, sub) {
  { gg.save(); gg.translate(W - 300, H - 110); gg.scale(2.6, 1); const q = gg.createRadialGradient(0, 0, 0, 0, 0, 260); q.addColorStop(0, 'rgba(4,12,22,.5)'); q.addColorStop(1, 'rgba(4,12,22,0)'); gg.fillStyle = q; gg.fillRect(-300, -260, 600, 520); gg.restore(); }
  gg.save(); gg.fillStyle = '#FFFFFF'; gg.textAlign = 'right'; gg.shadowColor = 'rgba(0,0,0,.55)'; gg.shadowBlur = 8;
  gg.font = font(500, 40);
  const CN = '①②③④⑤⑥⑦⑧⑨', ci = CN.indexOf(title[0]);
  if (ci < 0) gg.fillText('| ' + title + ' |', W - 120, H - 132);
  else {                                      // Pretendard's circled digits are small: draw the number badge at cap height
    const rest = title.slice(1).trim(), tail = ' ' + rest + ' |', tw = gg.measureText(tail).width, R = 17;
    gg.fillText(tail, W - 120, H - 132);
    const cx = W - 120 - tw - R - 4, cy = H - 132 - 15;
    gg.lineWidth = 2.6; gg.strokeStyle = '#FFFFFF'; gg.beginPath(); gg.arc(cx, cy, R, 0, 7); gg.stroke();
    gg.font = font(700, 25); gg.textAlign = 'center'; gg.textBaseline = 'middle'; gg.fillText(String(ci + 1), cx, cy + 1);
    gg.font = font(500, 40); gg.textAlign = 'right'; gg.textBaseline = 'alphabetic'; gg.fillText('| ', cx - R - 6, H - 132);
  }
  if (sub) { gg.font = font(400, 28); gg.globalAlpha = .9; gg.fillText(sub, W - 128, H - 88); }
  gg.restore();
}
const cv = document.getElementById('cv');
let SHOT = setupShot, EXTRA_GROUND = null, EXTRA_WORLD = null, POST = gm => caption(gm, '2030 · POSCO 청록수소 플랜트', '햇살 좋은 날, 수소 안전을 하나씩 점검합니다');
function render() {
  const dpr = Math.max(1, window.devicePixelRatio || 1), sc = Math.min(innerWidth / W, innerHeight / H);
  cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
  cv.style.width = W * sc + 'px'; cv.style.height = H * sc + 'px'; cv.style.left = (innerWidth - W * sc) / 2 + 'px'; cv.style.top = (innerHeight - H * sc) / 2 + 'px';
  SHOT(); const hy = horizonY();
  const B = mk(cv.width, cv.height); DPR = dpr; g = B.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  sky(g, hy);
  g.fillStyle = lg(0, Math.max(0, hy), 0, H, [[0, '#9DB596'], [.25, '#7E9F6B'], [1, '#6A8F57']]); g.fillRect(0, Math.max(0, hy), W, H - Math.max(0, hy));
  SEA_TOP = -9000; drawSea(); drawGroundPlan(); if (EXTRA_GROUND) EXTRA_GROUND(); drawForest(); solarField(); drawShadows(); drawSolar();
  OBJ.slice().sort((a, b) => a.depth - b.depth).forEach(o => o.f());
  if (EXTRA_WORLD) EXTRA_WORLD();
  const gm = cv.getContext('2d'); gm.setTransform(1, 0, 0, 1, 0, 0);
  gm.filter = 'contrast(1.12) saturate(.92)'; gm.drawImage(B, 0, 0); gm.filter = 'none';
  gm.setTransform(dpr, 0, 0, dpr, 0, 0); grade(gm, hy); POST(gm);
  window.__ready = true;
}
