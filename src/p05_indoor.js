
/* ============================================================
   SCENE ④ (indoor) — hydrogen compressor house
   Hydrogen is lighter than air: a leak rises and collects under the roof,
   so detectors sit at the ceiling and the roof is ventilated.
   Room: x 0..26 (length), y 0..16 (depth), z 0..9 (height).
   ============================================================ */
const HALL = { L:30, D:20, Hh:9 };
const LEAK4 = [8.4, 5.0, 3.15];
const UVIR4 = [[3.2, .35, 5.6], [12.4, .35, 5.6]];
const PSV4 = [5.4, 3.6, 4.35];
const GAUGE4 = [11.2, 7.4, 1.75];
const ZONE4 = [4.2, 2.6, 0, 18.4, 6.2, 4.6];
function camIndoor() { setCam([28.6, 19.2, 4.4], [10.5, 3.6, 2.1], 58); }
function polyV(pts, stops) {                          // filled polygon with a vertical screen-space gradient
  const sp = projPoly(pts); if (sp.length < 3) return; path(sp);
  const ys = sp.map(p => p[1]); const q = g.createLinearGradient(0, Math.min(...ys), 0, Math.max(...ys));
  stops.forEach(([o, c]) => q.addColorStop(o, c)); g.fillStyle = q; g.fill();
}
function polyH(pts, stops) {
  const sp = projPoly(pts); if (sp.length < 3) return; path(sp);
  const xs = sp.map(p => p[0]); const q = g.createLinearGradient(Math.min(...xs), 0, Math.max(...xs), 0);
  stops.forEach(([o, c]) => q.addColorStop(o, c)); g.fillStyle = q; g.fill();
}
function compressor(x0, y0) {
  box(x0, y0, 0, 7.4, 3.4, .35, '#47525E', { top:'#5C6875' });                               // skid frame
  box(x0 + .9, y0 + .5, .35, 3.2, 2.4, 1.7, '#3E6A9A', { top:'#5B86B8' });                   // crankcase
  box(x0 + 4.4, y0 + .7, .35, 2.4, 2.0, 1.45, '#2E5585', { top:'#47719F' });                 // motor
  for (let k = 0; k < 6; k++) line3([x0 + 6.8, y0 + .9 + k * .3, .5], [x0 + 6.8, y0 + .9 + k * .3, 1.7], 'rgba(20,30,45,.55)', 1);
  box(x0 + 4.1, y0 + 1.4, .9, .3, .6, .6, '#26476F', { edge:false });                       // coupling guard
  // two diaphragm heads on top: big bolted discs
  [[x0 + 1.7, y0 + 1.7], [x0 + 3.1, y0 + 1.7]].forEach(([cx, cy]) => {
    cyl(cx, cy, 2.05, .62, .5, '#C9D3DE', { bands:[[.12, 'rgba(60,70,85,.6)', .06], [.38, 'rgba(60,70,85,.6)', .06]] });
    cyl(cx, cy, 2.55, .42, .45, '#B7C3D0', { capColor:'#DCE3EA' });
    if (!HOLO) for (let a = 0; a < 6.283; a += .785) { const p = P(cx + Math.cos(a) * .55, cy + Math.sin(a) * .55, 2.56); g.fillStyle = '#4A5563'; g.beginPath(); g.arc(p[0], p[1], Math.max(1, .05 * S(cx, cy, 2.5)), 0, 7); g.fill(); }
  });
  // pulsation damper with safety valve and vent stack to the roof
  cyl(x0 + .4, y0 + .1, .35, .42, 3.4, '#E3E8EE', { dome:.3, bands:[[.4, PAL.tq, .1]] });
  pipe3([[x0 + 1.7, y0 + 1.7, 3.0], [x0 + 1.7, y0 + 1.7, 3.15], [x0 + .4, y0 + .1, 3.15]], .14, '#F1F4F7');
  pipe3([[x0 + 3.1, y0 + 1.7, 3.0], [x0 + 3.1, y0 + 1.7, 3.15], [x0 + 3.1, y0 - 1.0, 3.15], [x0 + 3.1, .45, 3.15]], .14, '#F1F4F7');
  flange(x0 + 3.1, y0 + .6, 3.15, 'y', .2, '#9AA6B4');
}
function drawHall() {
  const { L, D, Hh } = HALL;
  // ceiling with roof deck ribs
  polyV([[0, 0, Hh], [L, 0, Hh], [L, D, Hh], [0, D, Hh]], [[0, '#5D6873'], [1, '#7C8792']]);
  for (let x = 1; x < L; x += 1.2) line3([x, 0, Hh - .01], [x, D, Hh - .01], 'rgba(40,50,62,.35)', 1);
  // back wall (y = 0): insulated panels, dado band, high louvres
  polyV([[0, 0, 0], [L, 0, 0], [L, 0, Hh], [0, 0, Hh]], [[0, '#B5BEC6'], [.55, '#CCD3DA'], [1, '#DDE3E8']]);
  polyV([[0, .01, 0], [L, .01, 0], [L, .01, 1.2], [0, .01, 1.2]], [[0, '#7E8B97'], [1, '#93A0AC']]);
  for (let x = 2; x < L; x += 2) line3([x, .02, 0], [x, .02, Hh], 'rgba(90,100,112,.35)', 1);
  const LV = [3, 9, 15, 21, 27];
  LV.forEach(x => { polyV([[x, .02, 7.0], [x + 2.6, .02, 7.0], [x + 2.6, .02, 8.2], [x, .02, 8.2]], [[0, '#F4F1E6'], [1, '#FFFDF5']]);
    for (let z = 7.15; z < 8.2; z += .2) line3([x, .03, z], [x + 2.6, .03, z], 'rgba(90,96,104,.6)', 1.2); });
  // left wall (x = 0): roller door frame and MCC panels
  polyH([[0, 0, 0], [0, D, 0], [0, D, Hh], [0, 0, Hh]], [[0, '#C3CBD2'], [1, '#A9B3BC']]);
  polyV([[.01, 0, 0], [.01, D, 0], [.01, D, 1.2], [.01, 0, 1.2]], [[0, '#7A8794'], [1, '#8E9BA7']]);
  for (let y = 2; y < D; y += 2) line3([.02, y, 0], [.02, y, Hh], 'rgba(90,100,112,.3)', 1);
  // right wall (x = L), mostly behind the camera
  polyH([[L, 0, 0], [L, D, 0], [L, D, Hh], [L, 0, Hh]], [[0, '#B9C2CA'], [1, '#9EA8B2']]);
  // floor: epoxy, walkway lines, hatched keep-clear strips
  polyV([[0, 0, 0], [L, 0, 0], [L, D, 0], [0, D, 0]], [[0, '#7E8A86'], [1, '#97A39E']]);
  line3([0, 10.4, .01], [L, 10.4, .01], 'rgba(232,180,40,.95)', 3); line3([0, 11.6, .01], [L, 11.6, .01], 'rgba(232,180,40,.95)', 3);
  for (let x = .5; x < L; x += 1.4) line3([x, 10.4, .012], [x + .7, 11.6, .012], 'rgba(232,180,40,.35)', 2);
  // ceiling trusses and roof fans
  for (let x = 2.5; x < L; x += 5) { box(x - .15, 0, Hh - .55, .3, D, .55, '#4A5562', { top:'#5B6673', edge:false }); }
  [[6, 6], [13, 6], [20, 6], [27, 6]].forEach(([x, y]) => { const e = circ(x, y, Hh - .02, 1.0); g.fillStyle = '#2A3139'; g.beginPath(); g.ellipse(e[0], e[1], e[2], e[3], 0, 0, 7); g.fill();
    g.strokeStyle = 'rgba(160,170,180,.7)'; g.lineWidth = 1.2; for (let a = 0; a < 6.283; a += 1.047) { const p = P(x + Math.cos(a) * .85, y + Math.sin(a) * .85, Hh - .03), c = P(x, y, Hh - .03); g.beginPath(); g.moveTo(c[0], c[1]); g.lineTo(p[0], p[1]); g.stroke(); } });
  // hydrogen detectors at the ceiling (high point)
  [[8.4, 5.0], [15.5, 5.0]].forEach(([x, y]) => { line3([x, y, Hh - .55], [x, y, Hh - .9], '#7F8FA3', 1.2); box(x - .18, y - .18, Hh - 1.25, .36, .36, .35, '#F4F6F8', { edge:false }); });
  // structural column carrying a flame detector
  // linear lights
  [[5, 10], [12, 10], [19, 10], [26, 10], [5, 3], [12, 3], [19, 3], [26, 3]].forEach(([x, y]) => { line3([x, y, Hh - .55], [x, y, 7.6], '#5E6873', 1); box(x - 1.2, y - .1, 7.45, 2.4, .2, .15, '#F7F9FB', { edge:false, top:'#FFFFFF' }); });
  // piping along the back wall, valves
  pipe3([[.3, .45, 3.15], [L - .3, .45, 3.15]], .2, '#F1F4F7');
  pipe3([[.3, .9, 2.4], [L - .3, .9, 2.4]], .16, '#E2B42B');
  for (let x = 2; x < L; x += 4) { line3([x, .05, 3.0], [x, .7, 3.0], '#6E7F93', 1.4); flange(x + 1, .45, 3.15, 'x', .26, '#9AA6B4'); }
  [[6.4, .45], [17.4, .45]].forEach(([x, y]) => { box(x - .2, y - .2, 3.0, .4, .4, .35, '#5E6B7A', { edge:false }); handwheel(x, y, 3.55, .22, 'z'); });
  // aftercooler along the back
  hcyl(14, 22.5, 1.6, 1.25, .55, '#D6DDE4', { bands:[16, 20] });
  // compressors
  compressor(4.5, 3.0);
  compressor(14.4, 3.0);
  // pressure gauge on a post in front of compressor A
  line3([GAUGE4[0], GAUGE4[1], 0], [GAUGE4[0], GAUGE4[1], 1.35], '#7F8FA3', 2);
  if (!HOLO) { const p = P(GAUGE4[0], GAUGE4[1], GAUGE4[2]), k = S(...GAUGE4), R = .3 * k;
    g.fillStyle = '#2E3B4A'; g.beginPath(); g.arc(p[0], p[1], R * 1.15, 0, 7); g.fill(); g.fillStyle = '#FFFFFF'; g.beginPath(); g.arc(p[0], p[1], R, 0, 7); g.fill();
    const arc = (a0, a1, c) => { g.strokeStyle = c; g.lineWidth = R * .2; g.beginPath(); g.arc(p[0], p[1], R * .78, a0, a1); g.stroke(); };
    const A = t => Math.PI * .75 + t * Math.PI * 1.5; arc(A(0), A(.62), '#2E9E6A'); arc(A(.62), A(.8), '#E8B42B'); arc(A(.8), A(1), '#C0392B');
    const an = A(.88); g.strokeStyle = '#16202B'; g.lineWidth = Math.max(1.2, R * .1); g.beginPath(); g.moveTo(p[0], p[1]); g.lineTo(p[0] + Math.cos(an) * R * .8, p[1] + Math.sin(an) * R * .8); g.stroke(); }
  // flame detectors
  UVIR4.forEach(([x, y, z]) => box(x - .22, y - .12, z - .14, .44, .3, .3, '#2B3A4C', { edge:false, top:'#44566B' }));
  // safety valve (red) on the damper of compressor A, vent through the roof
  pipe3([[PSV4[0], PSV4[1], 4.6], [PSV4[0], PSV4[1], Hh + .5]], .12, '#B9C4CF');
  cyl(PSV4[0], PSV4[1], 3.75, .2, .6, '#C0392B', { capColor:'#E05A4A' });
  // worker with tablet near compressor B
  person(5.8, 10.0, -2.2, 'tablet'); person(9.0, 11.8, -1.9, 'stand');
}
function indoorFX() {
  const [lx, ly, lz] = LEAK4;
  // daylight shafts from the high louvres
  g.save(); g.globalCompositeOperation = 'lighter';
  [3, 9, 15, 21, 27].forEach(x => { const a = P(x, .05, 8.2), b = P(x + 2.6, .05, 8.2), c = P(x + 5.2, 9, 0), d = P(x + 2.6, 9, 0);
    const q = g.createLinearGradient(a[0], a[1], d[0], d[1]); q.addColorStop(0, 'rgba(255,240,210,.045)'); q.addColorStop(1, 'rgba(255,240,210,0)');
    g.fillStyle = q; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.lineTo(c[0], c[1]); g.lineTo(d[0], d[1]); g.closePath(); g.fill(); });
  g.restore();
  // explosion-protected zone round the compressors
  const [zx, zy, zz, zw, zd, zh] = ZONE4, Z = [[zx, zy], [zx + zw, zy], [zx + zw, zy + zd], [zx, zy + zd]];
  g.save(); g.setLineDash([9, 7]); g.strokeStyle = 'rgba(255,170,90,.9)'; g.lineWidth = 1.6;
  [zz, zz + zh].forEach(z => { const pts = Z.map(([x, y]) => P(x, y, z)); g.beginPath(); pts.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath(); g.stroke(); });
  Z.forEach(([x, y]) => { const a = P(x, y, zz), b = P(x, y, zz + zh); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); });
  g.setLineDash([]); g.fillStyle = 'rgba(255,170,90,.07)'; const fl = Z.map(([x, y]) => P(x, y, .02)); g.beginPath(); fl.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath(); g.fill();
  g.restore();
  // leaking hydrogen rises and spreads under the roof (faint, cool tint)
  g.save(); g.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 28; i++) { const k = i / 28, z = lz + k * (HALL.Hh - .7 - lz), p = P(lx + Math.sin(k * 4) * .3, ly, z), R = (.3 + k * 1.6) * S(lx, ly, z);
    const c = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], R); c.addColorStop(0, `rgba(160,215,255,${.035 * (1 - k * .4)})`); c.addColorStop(1, 'rgba(160,215,255,0)'); g.fillStyle = c; g.beginPath(); g.arc(p[0], p[1], R, 0, 7); g.fill(); }
  { const a = P(lx - 4, ly - 2, HALL.Hh - .4), b = P(lx + 4, ly + 2, HALL.Hh - .4), c = P(lx, ly, HALL.Hh - .4), R = Math.hypot(b[0] - a[0], b[1] - a[1]) / 2;
    const q = g.createRadialGradient(c[0], c[1], 0, c[0], c[1], R); q.addColorStop(0, 'rgba(170,220,255,.09)'); q.addColorStop(1, 'rgba(170,220,255,0)'); g.save(); g.translate(c[0], c[1]); g.scale(1, .35); g.translate(-c[0], -c[1]); g.fillStyle = q; g.beginPath(); g.arc(c[0], c[1], R, 0, 7); g.fill(); g.restore(); }
  g.restore();
  // nearly invisible flame: heat ripple at the head flange
  g.save(); g.strokeStyle = 'rgba(235,245,255,.45)'; g.lineWidth = 1.3;
  for (let s = -2; s <= 2; s++) { g.beginPath(); for (let z = 0; z < 1.6; z += .05) { const p = P(lx, ly, lz + .1 + z), k = S(lx, ly, lz + z); const x = p[0] + s * .12 * k + Math.sin(z * 7 + s * 1.3) * .07 * k * (1 + z); z === 0 ? g.moveTo(x, p[1]) : g.lineTo(x, p[1]); } g.stroke(); }
  g.restore();
  // UV/IR detection cones converging on the flange
  UVIR4.forEach(([x, y, z]) => { const a = P(x, y, z), b = P(lx, ly, lz + .5), dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L, w = L * .22;
    g.save(); const q = g.createLinearGradient(a[0], a[1], b[0], b[1]); q.addColorStop(0, 'rgba(255,190,120,.28)'); q.addColorStop(1, 'rgba(255,190,120,.04)');
    g.fillStyle = q; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0] + nx * w, b[1] + ny * w); g.lineTo(b[0] - nx * w, b[1] - ny * w); g.closePath(); g.fill(); g.restore(); });
}
function indoorHUD(gm) {
  scrim(gm, 970);
  const m = P(...LEAK4); hudMarker(gm, m[0], m[1], 4);
  hudTag(gm, 'UV/IR 화염검지', UVIR4[0][0], UVIR4[0][1], UVIR4[0][2] + .2, -240, -120);
  hudTag(gm, '안전밸브', PSV4[0], PSV4[1], PSV4[2] + .1, -150, -60);
  hudTag(gm, '고압', GAUGE4[0], GAUGE4[1], GAUGE4[2] + .3, -130, 60);
  hudTag(gm, '방폭 구역', ZONE4[0], ZONE4[1] + ZONE4[4], 0, -110, 50);
  hudPanel(gm, 1300, 230, 500,
    [['위험', '고압 · 눈에 잘 안 보이는 수소 불꽃 · 수소취성', 'risk'], ['안전조치', 'UV/IR 화염검지 · 안전밸브 · 방폭 구역', 'safe']],
    ['고압가스법 KGS 검사', '산안법 PSM']);
}
function renderIndoor(rq, withHUD = 'overlay') {
  const w = Math.round(W * rq), h = Math.round(H * rq);
  camIndoor(); DPR = rq;
  const B = mk(w, h); g = B.getContext('2d'); g.setTransform(rq, 0, 0, rq, 0, 0);
  g.fillStyle = '#2A3138'; g.fillRect(0, 0, W, H);
  drawHall(); indoorFX();
  const out = mk(w, h), gm = out.getContext('2d');
  gm.filter = 'contrast(1.1) saturate(.92)'; gm.drawImage(B, 0, 0); gm.filter = 'none';
  gm.setTransform(rq, 0, 0, rq, 0, 0); grade(gm, -400);
  let ov = null;
  if (withHUD === 'overlay') { ov = mk(w, h); const og = ov.getContext('2d'); og.setTransform(rq, 0, 0, rq, 0, 0); indoorHUD(og); }
  else if (withHUD === 'base') indoorHUD(gm);
  return { base: out, ov };
}
