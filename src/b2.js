
/* ============================================================
   ENVIRONMENT
   ============================================================ */
function drawSky() {
  g.fillStyle = lg(0, 0, 0, HORIZON, [[0, '#6FC0F2'], [.7, '#BFE5FA'], [1, '#E6F5FD']]); g.fillRect(0, 0, W, HORIZON + 2);
  const sx = 1580, sy = 92;
  const gr = g.createRadialGradient(sx, sy, 8, sx, sy, 420);
  gr.addColorStop(0, 'rgba(255,250,225,1)'); gr.addColorStop(.12, 'rgba(255,240,190,.75)'); gr.addColorStop(.4, 'rgba(255,240,200,.18)'); gr.addColorStop(1, 'rgba(255,240,200,0)');
  g.fillStyle = gr; g.fillRect(0, 0, W, HORIZON + 2);
  g.fillStyle = '#FFFBEA'; g.beginPath(); g.arc(sx, sy, 34, 0, Math.PI * 2); g.fill();
  // soft clouds
  [[250, 150, 1.0], [700, 176, .62], [1010, 128, .85], [1330, 196, .5], [1830, 205, .55], [80, 210, .42]].forEach(([x, y, s]) => cloud(x, y, s));
}
function cloud(x, y, s) {
  // cumulus: overlapping puffs, flat base, cool shading underneath
  const puffs = [[-120, -6, 38], [-70, -34, 52], [-10, -52, 66], [60, -36, 54], [118, -10, 40], [20, -12, 50], [-50, -8, 44]];
  g.save(); g.translate(x, y); g.scale(s, s);
  g.beginPath(); g.rect(-200, -160, 400, 160); g.clip();
  g.fillStyle = 'rgba(200,222,240,.9)'; g.beginPath(); puffs.forEach(([px, py, r]) => { g.moveTo(px + r, py + 6); g.arc(px, py + 6, r, 0, 7); }); g.fill();
  const cg = g.createLinearGradient(0, -120, 0, 0); cg.addColorStop(0, '#FFFFFF'); cg.addColorStop(.75, '#FAFDFF'); cg.addColorStop(1, '#E2EEF8');
  g.fillStyle = cg; g.beginPath(); puffs.forEach(([px, py, r]) => { g.moveTo(px + r, py); g.arc(px, py, r, 0, 7); }); g.fill();
  g.restore();
}
function ridge(y0, amp, seed, col0, col1, x0 = 0, x1 = W) {
  const r = rng(seed); g.beginPath(); g.moveTo(x0, HORIZON + 2);
  let a = r() * 6, b = r() * 6;
  for (let x = x0; x <= x1; x += 8) g.lineTo(x, y0 - amp * (.55 + .3 * Math.sin(x * .004 + a) + .15 * Math.sin(x * .013 + b)));
  g.lineTo(x1, HORIZON + 2); g.closePath(); g.fillStyle = lg(0, y0 - amp, 0, HORIZON, [[0, col0], [1, col1]]); g.fill();
}
function drawFarLand() {
  ridge(HORIZON - 6, 40, 3, '#A7C2D8', '#CFE0EC', 0, W);          // far mountains behind the steel works
  ridge(HORIZON, 26, 8, '#8FB49B', '#B6D2B4', 1050, W);
  g.fillStyle = '#B9D7A5'; g.fillRect(0, HORIZON, W, H - HORIZON);
}
const COAST = -14;
let SEA_TOP = HORIZON;
function drawSea() {
  g.save(); g.beginPath(); g.rect(-4000, SEA_TOP, 12000, 30000); g.clip();
  { const hy = horizonY(); poly3([[COAST, -90000], [COAST, 700], [-90000, 700], [-90000, -90000]], lg(0, hy, 0, H, [[0, '#9CC6DC'], [.18, '#4E97C2'], [1, '#155F90']])); }
  // wave glints
  const r = rng(12); g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 1.4;
  for (let i = 0; i < 700; i++) {
    const x = COAST - 6 - r() * 420, y = -220 + r() * 520; if (toCam(x, y, 0)[2] < NEAR) continue; const p = P(x, y, 0);
    if (p[1] < SEA_TOP + 4 || p[1] > H) continue;
    const k2 = S(x, y, 0), L = (1.2 + r() * 2.2) * k2; g.strokeStyle = `rgba(235,245,255,${.18 + r() * .25})`; g.lineWidth = Math.max(.6, .18 * k2); g.beginPath(); g.moveTo(p[0] - L, p[1]); g.lineTo(p[0] + L, p[1]); g.stroke();
  }
  // sun glitter path on the water
  
  // seawall + rocks along the coast
  poly3([[COAST, -260], [COAST + 5, -260], [COAST + 5, 260], [COAST, 260]], '#D9D2BE');
  poly3([[COAST - 3, -260], [COAST, -260], [COAST, 260], [COAST - 3, 260]], '#A99F88');
  const rr2 = rng(31);
  for (let y = -200; y < 240; y += 3.2) { const p = P(COAST - 2.5 - rr2() * 1.5, y, 0); g.fillStyle = rr2() > .5 ? '#BDB4A0' : '#9C937F'; g.beginPath(); g.arc(p[0], p[1], 1.6 + rr2() * 1.4, 0, 7); g.fill(); }
  ship(-74, 58, 40, 8, '#2F4F76'); ship(-44, 150, 18, 4.5, '#3E6A8F');
  g.restore();
}
function ship(x, y, L, Wd, c) {
  shBox(x, y, L, Wd, 0);
  box(x, y, -1.2, L, Wd, 3.2, c, { top: '#B44B3A' });
  box(x + L * .78, y + Wd * .15, 2, L * .14, Wd * .7, 6, '#F4F6F8');
  const cols = ['#C0392B', '#1BA39C', '#5B7FB5', '#E8772E', '#2E9E6A'];
  for (let i = 0; i < 7; i++) box(x + 3 + i * (L * .1), y + Wd * .12, 2, L * .085, Wd * .76, 2.4, cols[i % cols.length], { edge:false });
  // wake
  const p = P(x + L + 2, y + Wd / 2, 0); g.strokeStyle = 'rgba(255,255,255,.7)'; g.lineWidth = 2;
  g.beginPath(); g.moveTo(p[0], p[1]); g.lineTo(p[0] + 60, p[1] + 34); g.moveTo(p[0], p[1]); g.lineTo(p[0] + 70, p[1] + 18); g.stroke();
}
function road(pts, w = 7) {
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], L = Math.hypot(x1 - x0, y1 - y0), nx = -(y1 - y0) / L * w / 2, ny = (x1 - x0) / L * w / 2;
    const ex = (x1 - x0) / L * w / 2, ey = (y1 - y0) / L * w / 2;      // extend to overlap joints
    poly3([[x0 - ex + nx, y0 - ey + ny], [x1 + ex + nx, y1 + ey + ny], [x1 + ex - nx, y1 + ey - ny], [x0 - ex - nx, y0 - ey - ny]], PAL.asphalt);
    line3([x0 + nx * .9, y0 + ny * .9, 0], [x1 + nx * .9, y1 + ny * .9, 0], 'rgba(235,240,245,.55)', .8);
    line3([x0 - nx * .9, y0 - ny * .9, 0], [x1 - nx * .9, y1 - ny * .9, 0], 'rgba(235,240,245,.55)', .8);
    for (let d = 2; d < L - 2; d += 8) { const a = d / L, b2 = Math.min(1, (d + 4) / L); line3([x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, 0], [x0 + (x1 - x0) * b2, y0 + (y1 - y0) * b2, 0], 'rgba(255,255,255,.85)', Math.max(.8, .25 * S(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, 0))); }
  }
}
function drawGroundPlan() {
  // farmland patches beyond the site
  const r = rng(19); const fields = ['#C6DFB0', '#B2D59A', '#D2E5B6', '#A9CF92'];
  for (let i = 0; i < 26; i++) { const x = -10 + r() * 330, y = 150 + r() * 120, w = 18 + r() * 30, d = 14 + r() * 26; poly3([[x, y], [x + w, y], [x + w, y + d], [x, y + d]], fields[i % 4]); }
  for (let i = 0; i < 18; i++) { const x = 215 + r() * 120, y = -120 + r() * 260, w = 16 + r() * 30, d = 14 + r() * 26; poly3([[x, y], [x + w, y], [x + w, y + d], [x, y + d]], fields[(i + 1) % 4]); }
  // steel-works pad (behind)
  poly3([[96, -74], [222, -74], [222, -16], [96, -16]], '#D4D9DF');
  // plant site pad
  poly3([[0, 0], [205, 0], [205, 145], [0, 145]], PAL.concrete);
  // equipment bunds / pads
  [[22, 92, 22, 30], [50, 52, 40, 44], [88, 50, 50, 46], [136, 44, 60, 50], [4, 4, 38, 30], [138, 4, 64, 34], [50, 100, 36, 30]].forEach(([x, y, w, d]) => poly3([[x, y], [x + w, y], [x + w, y + d], [x, y + d]], '#D6DCE2', 'rgba(150,165,180,.6)', 1));
  // lawns
  [[2, 126, 18, 17], [50, 132, 78, 12], [50, 2, 80, 10], [2, 36, 40, 10]].forEach(([x, y, w, d]) => poly3([[x, y], [x + w, y], [x + w, y + d], [x, y + d]], '#A8D392'));
  // roads
  road([[-8, 150], [215, 150]], 8);                       // public road in front
  road([[212, 150], [212, -90]], 8);                     // road along right side
  road([[45, 0], [45, 145]], 6); road([[132, 0], [132, 145]], 6); road([[0, 96], [205, 96]], 6); road([[100, 145], [100, 150]], 6);
  road([[45, 0], [45, -10], [205, -10]], 6);
  // fence
  g.save(); g.setLineDash([3, 3]); poly3([[0, 0], [205, 0], [205, 145], [0, 145]], null, 'rgba(90,105,125,.8)', 1.2); g.restore();
  // parking beside the admin building
  poly3([[92, 104], [128, 104], [128, 126], [92, 126]], '#CDD3DA');
  g.strokeStyle = 'rgba(255,255,255,.8)'; for (let i = 0; i <= 10; i++) { line3([93 + i * 3.4, 105, 0], [93 + i * 3.4, 110, 0], 'rgba(255,255,255,.8)', .8); line3([93 + i * 3.4, 115, 0], [93 + i * 3.4, 120, 0], 'rgba(255,255,255,.8)', .8); }
  for (let i = 0; i < 9; i++) shBox(94 + i * 3.4, 105.4, 2, 4.2, 1.4);
  for (let i = 0; i < 6; i++) shBox(94 + i * 3.4, 115.4, 2, 4.2, 1.4);
  // loading-bay markings (front right)
  g.save(); g.setLineDash([4, 3]); poly3([[140, 100], [196, 100], [196, 140], [140, 140]], null, 'rgba(232,170,40,.9)', 1.4); g.restore();
}
// solar field (renewable power for the plant)
function solarField() {
  for (let row = 0; row < 7; row++) for (let seg = 0; seg < 5; seg++) {
    const x = 226 + seg * 13, y = 20 + row * 15;
    shBox(x, y, 11, 4, 1.6);
  }
}
function drawSolar() {
  for (let row = 0; row < 7; row++) for (let seg = 0; seg < 5; seg++) {
    const x = 226 + seg * 13, y = 20 + row * 15;
    poly3([[x, y, 2.6], [x + 11, y, 2.6], [x + 11, y + 4, .8], [x, y + 4, .8]], '#1F5FA6');
    g.strokeStyle = 'rgba(200,225,255,.55)'; g.lineWidth = .7;
    for (let k = 1; k < 6; k++) line3([x + k * 11 / 6, y, 2.6], [x + k * 11 / 6, y + 4, .8], 'rgba(200,225,255,.5)', .7);
    line3([x, y + 2, 1.7], [x + 11, y + 2, 1.7], 'rgba(200,225,255,.5)', .7);
    line3([x, y, 2.6], [x + 11, y, 2.6], 'rgba(255,255,255,.8)', .9);
  }
}
