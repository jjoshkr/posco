
/* ============================================================
   OBJECTS (registered with a depth key, drawn back-to-front)
   ============================================================ */
const OBJ = [];
let KIND = 'plant';
const add = (depth, f) => OBJ.push({ depth, f, kind: KIND });
const STEEL = '#C9D3DE', WHITE = '#EEF2F6', BLUEW = '#6F93C4';

KIND = 'env';
/* ---- cars in the car park ---- */
(() => { const cc = ['#F7FAFC', '#2B3A4C', '#C0392B', '#5B7FB5', '#F7FAFC', '#9AA8B8', '#1BA39C', '#F7FAFC', '#3D4B5C'];
  const car = (x, y, c) => add(x + y + 4, () => { box(x, y, 0, 2, 4.2, 1.0, c); box(x + .2, y + 1.2, 1, 1.6, 2.2, .6, '#3A4A5E', { top:'#7F9CC0' }); });
  for (let i = 0; i < 9; i++) car(94 + i * 3.4, 105.4, cc[i]);
  for (let i = 0; i < 6; i++) car(94 + i * 3.4, 115.4, cc[(i + 4) % 9]);
})();

KIND = 'plant';
/* ---- admin / control building (front, facing the road) ---- */
shBox(52, 104, 32, 16, 14);
add(52 + 32 + 104 + 16, () => {
  box(52, 104, 0, 32, 16, 14, '#F2F5F8', { top:'#DCE3EA' });
  windowsY(52, 120, 0, 32, 14, 3, 14, 'rgba(46,96,150,.78)');
  windowsX(84, 120, 0, 16, 14, 3, 7);
  box(52, 119.2, 13.2, 32, 1.2, .8, PAL.tq, { edge:false });
  box(56, 107, 14, 7, 5, 2.4, '#C9D3DE'); box(70, 108, 14, 9, 6, 1.6, '#AEBBCA');
  poly3([[56, 112, 14.1], [66, 112, 14.1], [66, 116, 14.1], [56, 116, 14.1]], '#2B5FA0');
  faceY(52, 120, 0, 32, 14, () => { g.save(); g.scale(1, -1);
    g.fillStyle = '#FFFFFF'; g.fillRect(2, -13.6, 28, 3.4);
    g.fillStyle = PAL.pb; g.font = font(800, 2.2); g.textBaseline = 'middle'; g.textAlign = 'center';
    g.fillText('POSCO 청록수소 플랜트 · 2030', 16, -11.9); g.restore(); });
  [[60, 124], [64, 124], [68, 124]].forEach(([x, y], i) => { line3([x, y, 0], [x, y, 9], '#9AA8B8', 1); poly3([[x, y, 9], [x + 3, y, 8.6], [x + 3, y, 7.2], [x, y, 7.6]], ['#1BA39C', '#004490', '#F7FAFC'][i]); });
});
/* ---- back-left: maintenance workshop + water tanks ---- */
shBox(6, 6, 28, 20, 10); shCyl(39, 12, 3.4, 9); shCyl(39, 24, 3.4, 9);
add(6 + 6 + 30, () => {
  box(6, 6, 0, 28, 20, 9, '#DDE5EC', { top:'#C9D3DE' });
  for (let i = 0; i < 4; i++) { const x = 6 + i * 7; poly3([[x, 6, 9], [x + 7, 6, 12], [x + 7, 26, 12], [x, 26, 9]], '#E9EFF5', 'rgba(80,100,125,.3)'); poly3([[x + 7, 6, 9], [x + 7, 6, 12], [x + 7, 26, 12], [x + 7, 26, 9]], 'rgba(150,190,230,.85)'); }
  faceY(6, 26, 0, 28, 9, () => { g.fillStyle = '#9AA8B8'; [3, 12, 21].forEach(u => g.fillRect(u, 0, 5, 6)); });
});
[[39, 12], [39, 24]].forEach(([x, y]) => add(x + y + 2, () => cyl(x, y, 0, 3.4, 9, '#DCE4EC', { dome:.9, bands:[[7.5, PAL.pb, .4]] })));
/* ---- back-right: utilities (cooling tower, nitrogen, water treatment) ---- */
shBox(142, 8, 26, 10, 8); shBox(144, 24, 12, 9, 6); shBox(176, 8, 19, 12, 4);
add(142 + 8 + 30, () => {
  box(142, 8, 0, 26, 10, 7, '#BCC8D5', { top:'#9FB0C2' });
  for (let i = 0; i < 4; i++) { const c = P(145.5 + i * 6.2, 13, 7.2); g.fillStyle = '#5C6B7D'; g.beginPath(); g.ellipse(c[0], c[1], 9, 5, 0, 0, 7); g.fill(); g.strokeStyle = '#D9E1EA'; g.lineWidth = 1; g.stroke(); }
  faceY(142, 18, 0, 26, 7, () => { g.fillStyle = 'rgba(80,95,115,.45)'; for (let i = 0; i < 26; i++) g.fillRect(i + .2, .6, .5, 5); });
});
add(144 + 24 + 20, () => { box(144, 24, 0, 12, 9, 6, '#EEF2F6'); windowsY(144, 33, 0, 12, 6, 1, 4); });
add(186 + 20 + 6, () => { [[176, 10], [176, 18]].forEach(([x, y]) => { box(x + 2, y - 1.2, 0, 1, 2.4, 1.8, '#7F8FA3'); box(x + 12, y - 1.2, 0, 1, 2.4, 1.8, '#7F8FA3'); hcyl(x + .8, x + 14.8, y, 3, 1.5, '#E3E8EE', { bands:[x + 4, x + 12] }); }); });
/* ---- solid-carbon product warehouse (back middle) ---- */
shBox(90, 6, 36, 18, 11);
add(90 + 6 + 40, () => {
  box(90, 6, 0, 36, 18, 10, '#E2E8EE', { top:'#C9D3DE' });
  poly3([[90, 6, 10], [126, 6, 10], [126, 15, 13], [90, 15, 13]], '#D3DCE5'); poly3([[90, 15, 13], [126, 15, 13], [126, 24, 10], [90, 24, 10]], '#EEF3F7');
  poly3([[126, 6, 10], [126, 15, 13], [126, 24, 10]], '#C3CDD8');
  box(90, 23.6, 7.6, 36, .4, .8, PAL.tq, { edge:false });
  faceY(90, 24, 0, 36, 10, () => { g.fillStyle = '#9AA8B8'; [3, 12, 21, 30].forEach(u => g.fillRect(u, 0, 4.5, 6)); });
});
KIND = 'plant';
/* ---- loading bay: tube-trailer filling canopy, carbon trucks ---- */
SHADOWS.push({ k:'box', x:145 + 6 * SUN.dx, y:107 + 6 * SUN.dy, w:22, d:20, h:0 });
add(160 + 120 + 8, () => {
  [[146, 108], [166, 108], [146, 126], [166, 126]].forEach(([x, y]) => line3([x, y, 0], [x, y, 6], '#8796A8', 1.6));
  [[150, 117], [158, 117]].forEach(([x, y]) => box(x, y - 1, 0, 1.6, 2, 2.2, '#F2F5F8', { top:PAL.tq }));          // dispensers
  poly3([[145, 107, 6], [167, 107, 6], [167, 127, 6], [145, 127, 6]], 'rgba(240,244,248,.96)', 'rgba(120,135,155,.6)', 1);
  poly3([[145, 127, 6], [167, 127, 6], [167, 127, 5.2], [145, 127, 5.2]], PAL.tq);
  poly3([[167, 107, 6], [167, 127, 6], [167, 127, 5.2], [167, 107, 5.2]], shade(PAL.tq, -.15));
});
KIND = 'env';
(() => { const trailer = (x, y) => add(x + y + 14, () => { box(x, y, 0, 13, 3, .8, '#4C5967'); for (let k = 0; k < 3; k++) pipe3([[x + .6, y + .6 + k * .9, 1.3 + (k % 2) * .5], [x + 12.4, y + .6 + k * .9, 1.3 + (k % 2) * .5]], .9, '#F4F7FA'); box(x + 13.2, y + .1, 0, 3.4, 2.8, 2.4, PAL.tq); });
  [[172, 110], [172, 117], [172, 124], [150, 132]].forEach(([x, y]) => trailer(x, y)); })();
KIND = 'plant';
/* ---- gate house ---- */
add(100 + 142 + 4, () => { box(102, 140, 0, 5, 3.5, 3.2, '#F2F5F8', { top:PAL.tq }); line3([96, 146, 1.2], [104, 146, 1.2], '#C0392B', 1.6); });

KIND = 'env';
for (const [x, y, s] of [[4, 40, 1], [16, 40, .9], [30, 40, 1], [-4, 66, 1.1], [-4, 82, 1], [-4, 100, 1.2], [-4, 118, 1.1], [-4, 134, 1], [10, 140, .9], [54, 136, 1], [66, 137, .9], [78, 136, 1], [90, 132, .8], [118, 140, 1], [150, 143, 1.1], [180, 143, 1], [200, 143, .9], [208, 118, 1], [208, 90, 1.1], [208, 60, 1], [208, 30, 1.1], [130, 4, .9], [60, 6, .8], [88, 6, .9]])
  add(x + y + .5, () => tree(x, y, s * .62, x * 7 + y));

KIND = 'plant';
/* ---- ① feed intake & pretreatment (detailed for close-ups) ----
   zone x 6..41, y 101..126; city-gas lines are painted yellow as in Korean practice */
const GASY = '#E2B42B';
shBox(8, 112, 9, 10, 4.6); shCyl(37, 106.5, 1.7, 10); shCyl(37, 112.5, 1.7, 10); shCyl(9, 104, .4, 11);
add(6 + 101 + 1, () => {
  poly3([[6, 101], [41, 101], [41, 126], [6, 126]], '#BFC6CD');
  for (let x = 6; x <= 41; x += 5) line3([x, 101, .02], [x, 126, .02], 'rgba(140,150,162,.45)', .6);
  for (let y = 101; y <= 126; y += 5) line3([6, y, .02], [41, y, .02], 'rgba(140,150,162,.45)', .6);
  // yellow walkway edge lines
  line3([6.5, 110.6, .03], [40.5, 110.6, .03], 'rgba(232,180,40,.9)', 1.2); line3([6.5, 111.4, .03], [40.5, 111.4, .03], 'rgba(232,180,40,.9)', 1.2);
  // hatched keep-clear zone round the shut-off valve
  for (let i = 0; i < 6; i++) line3([15.5 + i, 127, .03], [16.5 + i, 129.5, .03], 'rgba(232,180,40,.95)', 1.4);
});
add(8 + 112 + 14, () => {                                          // gas metering station
  box(8, 112, 0, 9, 10, 4.6, '#E9EDF1', { top:'#CBD3DC' });
  box(8, 121.4, 3.9, 9, .6, .5, PAL.tq, { edge:false });
  faceY(8, 122, 0, 9, 4.6, () => { g.fillStyle = 'rgba(110,125,145,.55)'; for (let i = 0; i < 9; i++) g.fillRect(.6 + i * .9, 1.2, .45, 2.2); });
  faceX(17, 122, 0, 10, 4.6, () => { g.fillStyle = '#AEB9C6'; g.fillRect(-4.2, 0, 1.6, 2.6); g.fillStyle = 'rgba(110,125,145,.55)'; for (let i = 0; i < 5; i++) g.fillRect(-9.4 + i * .8, 2.4, .4, 1.4); });
  [[10.5, 115], [14, 118.5]].forEach(([x, y]) => { ell(x, y, 4.62, 1.1); g.fillStyle = '#5C6B7D'; g.fill(); ell(x, y, 4.7, .55); g.fillStyle = '#8796A8'; g.fill(); });   // roof vent fans
});
add(9 + 104 + 2, () => { cyl(9, 104, 0, .35, 11, '#B9C4CF', { cap:'flat' }); cyl(9, 104, 11, .55, .3, '#8796A8'); });    // vent stack
add(10 + 103 + 2, () => { box(10, 103, 0, 2.2, 1, 1.9, '#9AA8B8', { top:'#C3CCD6' }); box(39, 124, 0, .5, .5, .9, '#C0392B', { edge:false }); });   // e-panel, extinguisher
// buried city-gas main from the street + above-ground riser
add(18 + 160, () => {
  g.save(); g.setLineDash([7, 6]); { const p1 = P(18, 330, 0), p2 = P(18, 146, 0); g.strokeStyle = rgba(GASY, .8); g.lineWidth = 3; g.beginPath(); g.moveTo(p1[0], p1[1]); g.lineTo(p2[0], p2[1]); g.stroke(); } g.restore();
  box(16.8, 141.2, 0, 2.4, 2, 1.4, '#F2C14E', { top:'#F7D77A' });
});
// inlet with emergency shut-off valve
add(18 + 128, () => {
  pipe3([[18, 142, .9], [18, 126, .9], [14, 126, .9], [14, 122, .9]], .5, GASY);
  flange(18, 134, .9, 'y', .45); flange(18, 129, .9, 'y', .45);
  box(17.55, 130.6, .35, .9, 1.6, 1.1, '#5E6B7A');                  // valve body
  box(17.4, 131, 1.45, 1.2, .8, .9, '#C0392B', { top:'#E05A4A' });   // actuator (ESD)
  handwheel(18, 131.4, 2.6, .45, 'z');
});
// header + filter separators
add(20 + 110 + 3, () => {
  pipe3([[17, 117, 1.2], [20, 117, 1.2], [20, 104, 1.2]], .45, GASY);
  [104, 109].forEach(y => { pipe3([[20, y, 1.2], [20, y, 3.95], [22, y, 3.95]], .4, GASY); flange(20, y, 3.95, 'x', .38); });
  flange(20, 113, 1.2, 'y', .32, '#9AA6B4');                                    // the flange used for the leak scene
  [104, 109].forEach(y => {
    [22.5, 31.5].forEach(x => box(x - .5, y - 1, 0, 1, 2, 1.3, '#7F8FA3', { edge:false }));      // saddles
    hcyl(21.5, 33, y, 2.5, 1.3, '#DDE3E9', { bands:[24, 30.5] });
    cyl(23, y, 3.6, .25, .5, '#AEB9C6'); cyl(30, y, 3.6, .25, .7, '#AEB9C6');                    // top nozzles
    const pg = P(26.5, y + 1.32, 3.1); g.fillStyle = '#FFFFFF'; g.beginPath(); g.arc(pg[0], pg[1], .22 * S(26.5, y, 3), 0, 7); g.fill(); g.strokeStyle = '#3E4C5E'; g.lineWidth = .8; g.stroke();
    pipe3([[31, y, 3.7], [31, y, 5.2], [37, y, 5.2], [37, y + (y === 104 ? 1.5 : 2.5), 5.2]], .4, GASY);
  });
});
// desulfurisers with platform and ladder
add(37 + 110 + 6, () => {
  frame(35, 104.3, 0, 4.4, 10.4, 9, 1, '#41679E', 'rgba(140,155,175,.6)', 'floors');
  cyl(37, 106.5, 0, 1.7, 10, '#E3E8EE', { dome:1, bands:[[1.2, PAL.tq, .25], [8.6, '#8C99A8', .2]] });
  cyl(37, 112.5, 0, 1.7, 10, '#E3E8EE', { dome:1, bands:[[1.2, PAL.tq, .25], [8.6, '#8C99A8', .2]] });
  frame(35, 104.3, 0, 4.4, 10.4, 9, 1, '#41679E', null, 'beams');
  for (let z = .4; z < 9; z += .45) line3([39.4, 115, z], [39.4, 115.6, z], '#7F8FA3', .8);
  line3([39.4, 115, 0], [39.4, 115, 10], '#7F8FA3', 1); line3([39.4, 115.6, 0], [39.4, 115.6, 10], '#7F8FA3', 1);
  pipe3([[37, 109.5, 11.2], [37, 99.5, 11.2], [26, 99.5, 11.2], [26, 88, 7.5]], .55, GASY);
  [[37, 106.5], [37, 112.5]].forEach(([x, y]) => pipe3([[x, y, 11], [x, y, 11.2], [37, 109.5, 11.2]], .4, GASY));
});
// gas detectors
[[19.5, 114.2], [30, 113.2], [33.8, 102.5]].forEach(([x, y]) => add(x + y + 2, () => {
  line3([x, y, 0], [x, y, 2.6], '#7F8FA3', Math.max(1, .1 * S(x, y, 1)));
  box(x - .2, y - .2, 2.6, .4, .4, .45, '#F4F6F8', { edge:false });
  const l = P(x, y + .21, 2.85); g.fillStyle = '#2E9E6A'; g.beginPath(); g.arc(l[0], l[1], Math.max(1, .07 * S(x, y, 2.8)), 0, 7); g.fill();
}));
// zone fence
add(6 + 126 + 1, () => {
  const fence = [[6, 101], [6, 126], [15, 126]], fence2 = [[21, 126], [41, 126]];
  [fence, fence2].forEach(f => { for (let i = 0; i < f.length - 1; i++) { const [a, b] = [f[i], f[i + 1]], L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    for (let d = 0; d <= L; d += 3) { const x = a[0] + (b[0] - a[0]) * d / L, y = a[1] + (b[1] - a[1]) * d / L; line3([x, y, 0], [x, y, 1.8], 'rgba(120,135,150,.55)', .7); }
    line3([a[0], a[1], 1.8], [b[0], b[1], 1.8], 'rgba(120,135,150,.9)', .8); line3([a[0], a[1], .9], [b[0], b[1], .9], 'rgba(120,135,150,.5)', .6); } });
});
// people
add(27 + 117 + 3, () => { person(26.5, 116.5, -2.3, 'tablet'); person(24.2, 115.6, -1.9, 'point', '#2C6CB5'); });

/* ---- main pipe rack linking the units ---- */
function rack(x0, x1, y, z, cols) {
  for (let x = x0; x <= x1; x += 8) { line3([x, y, 0], [x, y, z], '#6E7F93', 1.6); line3([x, y + 3, 0], [x, y + 3, z], '#6E7F93', 1.6); line3([x, y, z], [x, y + 3, z], '#6E7F93', 1.6); }
  cols.forEach(([dy, c, w], i) => pipe3([[x0, y + dy, z + .5], [x1, y + dy, z + .5]], w, c));
}
add(30 + 48 + 40, () => rack(30, 52, 47, 7, [[.6, PAL.tq, .9], [1.6, WHITE, .9], [2.5, '#B7C3D0', .7]]));
add(90 + 48 + 40, () => rack(78, 140, 47, 7, [[.6, PAL.tq, .9], [1.6, WHITE, .9], [2.5, '#B7C3D0', .7]]));
add(30 + 100, () => { for (let y = 88; y >= 52; y -= 8) { line3([25, y, 0], [25, y, 7.5], '#6E7F93', 1.3); line3([27, y, 0], [27, y, 7.5], '#6E7F93', 1.3); line3([25, y, 7.5], [27, y, 7.5], '#6E7F93', 1.3); }
  [[25, 97], [36, 98]].forEach(([x, y]) => { line3([x, y, 0], [x, y, 11.2], '#6E7F93', 1.3); line3([x + 2, y, 0], [x + 2, y, 11.2], '#6E7F93', 1.3); line3([x, y, 11.2], [x + 2, y, 11.2], '#6E7F93', 1.3); });
  pipe3([[26, 88, 7.5], [26, 50, 7.5], [30, 48.65, 7.5], [52, 48.65, 7.5]], 1.1, GASY); });

/* ---- ② pyrolysis reactor block (detailed) + plasma power ---- */
const REACT = [[59, 61], [66, 61], [73, 61], [62.5, 68], [69.5, 68]];
function facing(cx, cy, r) { const v = nrm([CAMR.p[0] - cx, CAMR.p[1] - cy, 0]); return [cx + v[0] * r, cy + v[1] * r]; }
shBox(54, 56, 24, 18, 40); shBox(54, 78, 20, 12, 10); shBox(76, 79, 7, 10, 4);
add(54 + 56 + 30, () => {
  box(52, 54, 0, 28, 22, .8, '#AEB9C6');
  frame(54, 56, .8, 24, 18, 28, 3, '#41679E', 'rgba(150,165,185,.5)', 'floors');
  REACT.forEach(([cx, cy], i) => {
    const h = i < 3 ? 36 : 33;
    cyl(cx, cy, .8, 2.7, 13, '#A9B3BE', { cap:'none', bands:[[3, 'rgba(70,85,105,.5)', .12], [6.5, 'rgba(70,85,105,.5)', .12], [10, 'rgba(70,85,105,.5)', .12]] });   // refractory-lined hot zone
    cyl(cx, cy, 13.8, 2.6, h - 13, '#E3E9EF', { dome:1.6, bands:[[0, PAL.tq, .5], [11, PAL.pb, .3], [17, PAL.tq, .25]] });
    cyl(cx, cy, 13, 2.85, .8, '#7F8FA3', { cap:'none' });                                                    // flange ring
    // plasma torch head + cable
    cyl(cx, cy, h + 2.2, .7, 2.2, '#5E6B7A', { capColor:'#8796A8' });
    if (HOLO) return;
    // sight windows (glow is added in the scene pass)
    const [fx, fy] = facing(cx, cy, 2.72);
    [7.2, 10.6].forEach(z => { const p = P(fx, fy, z), k = S(fx, fy, z);
      g.fillStyle = '#3B2A22'; g.beginPath(); g.ellipse(p[0], p[1], .55 * k, .75 * k, 0, 0, 7); g.fill();
      g.fillStyle = lg(0, p[1] - .7 * k, 0, p[1] + .7 * k, [[0, '#FFF1C4'], [.45, '#FFA444'], [1, '#D3542A']]); g.beginPath(); g.ellipse(p[0], p[1], .42 * k, .6 * k, 0, 0, 7); g.fill(); });
    // thermocouple ports at several heights
    [4.5, 9, 16, 24].forEach(z => { const [tx, ty] = facing(cx, cy, 2.95); box(tx - .2, ty - .2, z, .4, .4, .35, '#2E3B4A', { edge:false }); });
  });
  frame(54, 56, .8, 24, 18, 28, 3, '#41679E', null, 'beams');
  // stair tower
  box(78.5, 70, .8, 4, 4, 30, '#5B7FB5', { top:'#7FA0CC', left:'rgba(60,95,150,.55)', right:'rgba(80,115,170,.45)' });
  for (let k = 0; k < 10; k++) line3([82.5, 70, 2 + k * 3], [82.5, 74, 3.5 + k * 3], 'rgba(242,193,78,.95)', 1);
  // hot product header to the carbon separation unit (insulated)
  REACT.forEach(([cx, cy]) => pipe3([[cx, cy, 2.2], [cx, 63.5, 2.2]], .9, '#D5DCE3'));
  pipe3([[58, 63.5, 2.2], [86, 63.5, 2.2], [89, 64, 11], [91, 64, 16]], 1.3, '#D5DCE3', { gloss:.7 });
  // feed riser and top header (yellow city gas after pretreatment)
  pipe3([[52, 48.65, 7.5], [55.5, 50, 7.5], [55.5, 57, 7.5], [55.5, 57, 30.5], [76, 57, 30.5]], .55, GASY);
  REACT.forEach(([cx, cy]) => pipe3([[cx, 57, 30.5], [cx, cy - 1.8, 30.5], [cx, cy - .6, 31.5]], .3, GASY));
  // plasma DC bus duct from the power building to the reactor tops
  pipe3([[64, 80, 10.2], [64, 76, 10.2], [64, 75, 32.5], [59, 75, 32.5], [59, 61, 38.6]], .4, '#4A5A6E', { gloss:.3 });
  pipe3([[64, 75, 32.5], [73, 75, 32.5], [73, 61, 38.6]], .35, '#4A5A6E', { gloss:.3 });
  [[62.5, 68], [69.5, 68]].forEach(([x, y]) => pipe3([[x, 75, 32.5], [x, y, 35.6]], .3, '#4A5A6E', { gloss:.3 }));
  line3([66, 61, 38.5], [66, 61, 43], '#C0392B', 1.4); if (!HOLO) { g.fillStyle = '#FF5A4A'; const bp = P(66, 61, 43.4); g.beginPath(); g.arc(bp[0], bp[1], 2.2, 0, 7); g.fill(); }
});
// interlock shut-off valve + check valve on the feed line, upstream of the structure (clearly visible)
add(132, () => {
  box(41.9, 47.7, 6.4, 2.4, 1.9, 2.2, '#5E6B7A');                         // valve body
  box(41.8, 47.6, 8.6, 2.6, 2.1, 1.6, '#C0392B', { top:'#E05A4A' });       // actuator
  handwheel(43.1, 48.65, 10.5, .8, 'z');
  flange(41.6, 48.65, 7.5, 'x', .75); flange(44.6, 48.65, 7.5, 'x', .75);
  box(47.4, 47.9, 6.7, 1.8, 1.5, 1.7, '#4E6A86', { top:'#6F8DAA' });       // check valve (non-return)
  { const a = P(47.4, 49.41, 7.55), b = P(49.2, 49.41, 7.55); g.strokeStyle = '#FFFFFF'; g.lineWidth = 2; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.lineTo(b[0] - 5, b[1] - 4); g.moveTo(b[0], b[1]); g.lineTo(b[0] - 4, b[1] + 4); g.stroke(); }
  flange(47.2, 48.65, 7.5, 'x', .7); flange(49.4, 48.65, 7.5, 'x', .7);
  [[41.2, 47.6], [48, 47.6]].forEach(([x, y]) => { line3([x, y, 0], [x, y, 7], '#6E7F93', 1.4); line3([x, y + 2, 0], [x, y + 2, 7], '#6E7F93', 1.4); line3([x, y, 7], [x, y + 2, 7], '#6E7F93', 1.4); });
});
// people on the first platform level and at the base
add(64 + 74 + 2, () => { person(60, 73.2, -1.6, 'tablet', '#2C6CB5', 10.13); person(62, 73.5, -2.0, 'point', '#2C6CB5', 10.13); person(76, 77, -2.4, 'stand'); });
add(54 + 78 + 25, () => {
  box(54, 78, 0, 20, 12, 10, '#E9EEF3', { top:'#D2DAE3' });              // plasma power building
  box(54, 89.4, 8.6, 20, .6, 1.2, PAL.tq, { edge:false });
  windowsY(54, 90, 0, 20, 10, 2, 8, 'rgba(46,96,150,.6)');
  faceX(74, 90, 0, 12, 10, () => { g.fillStyle = 'rgba(120,135,155,.55)'; for (let i = 0; i < 10; i++) g.fillRect(-11 + i * 1.05, 2, .5, 5); });
  box(57, 80, 10, 5, 4, 1.6, '#AEBBCA'); box(66, 81, 10, 6, 5, 1.2, '#AEBBCA');
});
add(76 + 79 + 12, () => {                                                    // rectifier transformers
  [[76.5, 79.5], [76.5, 83.5], [76.5, 87.5]].forEach(([x, y]) => { box(x, y, 0, 5.5, 3, 3.4, '#8797AB', { top:'#A6B3C2' }); for (let k = 0; k < 6; k++) line3([x + 5.5, y + .3 + k * .45, .5], [x + 5.5, y + .3 + k * .45, 3.1], '#6B7B8F', .8); cyl(x + 1.5, y + 1.5, 3.4, .25, .9, '#C9D3DE'); cyl(x + 3.8, y + 1.5, 3.4, .25, .9, '#C9D3DE'); });
  pipe3([[76.5, 84, 2.5], [74, 84, 2.5]], .35, '#38475A');
});

// substation + lattice pylon + lines from the solar field
shBox(30, 72, 12, 14, 4);
add(30 + 72 + 22, () => {
  box(30, 72, 0, 12, 14, .5, '#B7C2CE');
  [[31, 73], [37, 73], [31, 80], [37, 80]].forEach(([x, y]) => { box(x, y, .5, 4, 4.5, 4, '#8797AB'); for (let k = 0; k < 4; k++) line3([x + 4, y + .6 + k, .9], [x + 4, y + .6 + k, 4], '#6B7B8F', .8); });
  g.save(); g.setLineDash([2, 2]); poly3([[29, 71], [43, 71], [43, 87], [29, 87]], null, 'rgba(90,105,125,.8)', 1); g.restore();
});
function pylon(x, y, h) { line3([x - 1.4, y, 0], [x, y, h], '#7A8798', 1.2); line3([x + 1.4, y, 0], [x, y, h], '#7A8798', 1.2); line3([x - 2.4, y, h - 3], [x + 2.4, y, h - 3], '#7A8798', 1.2); line3([x - 2, y, h - 6], [x + 2, y, h - 6], '#7A8798', 1.2); }
add(46 + 74, () => { pylon(46, 74, 14); });
// solar inverter station at the edge of the PV field
shBox(220, 6, 8, 5, 3.2);
add(220 + 6 + 10, () => { box(220, 6, 0, 8, 5, 3.2, '#F2F5F8', { top:'#C9D3DE' }); box(220, 10.6, 2.4, 8, .4, .5, PAL.tq, { edge:false }); });

/* ---- ③ carbon separation + storage (detailed) ----
   cyclones -> bag filter house -> gallery to silo tops; silos on legs discharge through
   rotary valves onto an open belt that feeds the big-bag station; dust extraction hood over the transfer point */
const SILOS = [[114, 82], [122, 82], [130, 82]];
shCyl(93, 64, 2.2, 22); shCyl(99, 64, 2.2, 22); shBox(104, 54, 12, 9, 16);
SILOS.forEach(([x, y]) => shCyl(x, y, 3.6, 35)); shBox(134.5, 79, 6, 6, 8);
add(93 + 64 + 6, () => {
  frame(90, 60, 0, 12, 8, 12, 2, '#41679E');
  [[93, 64], [99, 64]].forEach(([x, y]) => { cyl(x, y, 14, 2.2, 7, STEEL, { cap:'flat' }); cone(x, y, 14, 2.2, 6, .5, STEEL); });
  box(104, 54, 0, 12, 9, 16, '#DDE4EB', { top:'#C9D3DE' });                // bag-filter house
  faceY(104, 63, 0, 12, 16, () => { g.fillStyle = 'rgba(110,125,145,.45)'; for (let i = 0; i < 6; i++) g.fillRect(1 + i * 1.8, 3, 1.1, 11); });
  cyl(108, 52, 16, .5, 4, '#B9C4CF', { cap:'flat' });                      // clean-air stack
  pipe3([[96, 64, 21], [96, 64, 24], [110, 58, 24], [110, 58, 16]], 1.2, '#B7C3D0');
});
add(122 + 82 + 6, () => {
  box(110, 76, 0, 24, 12, .6, '#AEB9C6');
  SILOS.forEach(([x, y]) => {
    [[-2.6, -2.6], [2.6, -2.6], [2.6, 2.6], [-2.6, 2.6]].forEach(([dx, dy]) => line3([x + dx, y + dy, .6], [x + dx, y + dy, 9.4], '#5B7FB5', Math.max(1.5, .35 * S(x, y, 5))));
    line3([x - 2.6, y + 2.6, 2], [x + 2.6, y + 2.6, 8], 'rgba(91,127,181,.7)', 1.2); line3([x + 2.6, y - 2.6, 2], [x + 2.6, y + 2.6, 8], 'rgba(91,127,181,.7)', 1.2);
    cone(x, y, 10, 3.6, 5, .6, '#D7DEE6');                                                     // discharge cone
    box(x - .6, y - .6, 3.6, 1.2, 1.2, 1.4, '#4E5B6A', { top:'#6B7887' });                     // rotary valve
    pipe3([[x, y, 3.6], [x, y, 2.6]], .7, '#8796A8');                                         // chute to belt
    cyl(x, y, 10, 3.6, 21, '#E4EAF0', { cone:3.6, bands:[[1, '#8C99A8', .35], [12, '#3C434D', 1.0], [19, PAL.tq, .55]] });
    // grounding strap (green/yellow) from the leg to an earth pit
    { const a = P(x + 2.6, y + 2.6, 1.2), b = P(x + 3.6, y + 3.4, 0); g.save(); g.setLineDash([3, 3]); g.strokeStyle = '#E8C53A'; g.lineWidth = 2; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); g.lineDashOffset = 3; g.strokeStyle = '#2E9E6A'; g.stroke(); g.restore(); }
  });
  box(111, 80.6, 34.5, 22, 2.8, .8, '#7F8FA3', { edge:false });                               // roof catwalk
  for (let x = 111; x <= 133; x += 2) line3([x, 83.4, 35.3], [x, 83.4, 36.4], 'rgba(242,193,78,.95)', 1);
  line3([111, 83.4, 36.4], [133, 83.4, 36.4], 'rgba(242,193,78,.95)', 1.2);
  // inclined enclosed gallery from the filter house to the silo tops
  poly3([[110, 62, 14], [112, 80, 34.5], [114, 80, 34.5], [112, 62, 14]], '#9DAAB9');
  poly3([[110, 62, 16.5], [112, 80, 37], [114, 80, 37], [112, 62, 16.5]], '#C6D0DB');
  poly3([[112, 62, 14], [114, 80, 34.5], [114, 80, 37], [112, 62, 16.5]], '#B3BFCC');
});
// open belt conveyor under the silos, rising to the big-bag station
const BELT = [[110.5, 82, 2.2], [128, 82, 2.2], [136.5, 82, 7.2]];
add(124 + 84 + 8, () => {
  // stringers + legs
  for (let x = 111; x <= 128; x += 3.4) { line3([x, 81, 0], [x, 81, 2], '#6E7F93', 1.4); line3([x, 83, 0], [x, 83, 2], '#6E7F93', 1.4); }
  [[131, 4], [134, 5.8]].forEach(([x, z]) => { line3([x, 81, 0], [x, 81, z - .2], '#6E7F93', 1.4); line3([x, 83, 0], [x, 83, z - .2], '#6E7F93', 1.4); });
  for (let i = 0; i < BELT.length - 1; i++) { const [a, b] = [BELT[i], BELT[i + 1]];
    poly3([[a[0], 81, a[2]], [b[0], 81, b[2]], [b[0], 83, b[2]], [a[0], 83, a[2]]], '#2A2F36');                     // belt
    poly3([[a[0], 83, a[2] - .45], [b[0], 83, b[2] - .45], [b[0], 83, b[2]], [a[0], 83, a[2]]], '#7F8FA3');           // side stringer
    poly3([[a[0], 81.55, a[2] + .12], [b[0], 81.55, b[2] + .12], [b[0], 82.45, b[2] + .12], [a[0], 82.45, a[2] + .12]], '#111317');   // carbon black on the belt
    line3([a[0], 82.1, a[2] + .16], [b[0], 82.1, b[2] + .16], 'rgba(120,128,138,.35)', 1); }
  for (let x = 112; x < 136; x += 3.6) { const z = x <= 128 ? 2.2 : 2.2 + (x - 128) / 8.5 * 5; cyl(x, 83.1, z - .5, .22, .01, '#9AA8B8', { cap:'flat' }); }
});
// big-bag (FIBC) filling station + filled bags on pallets
add(137.5 + 86 + 8, () => {
  frame(134.5, 79, 0, 6, 6, 8, 2, '#41679E', 'rgba(140,155,175,.55)', 'floors');
  cone(137.5, 82, 8, 1.6, 2, .45, '#B9C4CF');                                                     // receiving hopper
  box(136.9, 81.4, 4.2, 1.2, 1.2, 1.6, '#4E5B6A', { top:'#6B7887' });                             // filling head
  box(136.4, 80.9, .2, 2.2, 2.2, 2.4, '#F2F2EE', { top:'#FFFFFF' });                               // bag being filled
  frame(134.5, 79, 0, 6, 6, 8, 2, '#41679E', null, 'beams');
  [[136, 87], [138.6, 87], [136, 89.6], [138.6, 89.6]].forEach(([x, y], i) => { if (i === 3) return;
    box(x, y, 0, 2.2, 2.2, .25, '#B98B57', { top:'#CFA26A' }); box(x + .1, y + .1, .25, 2, 2, 1.9, '#ECEDE8', { top:'#F8F8F5' });
    [[.4, .4], [1.6, .4], [.4, 1.6], [1.6, 1.6]].forEach(([dx, dy]) => line3([x + .1 + dx, y + .1 + dy, 2.15], [x + .1 + dx, y + .1 + dy, 2.55], '#D8D3C4', 1.2)); });
  // dust sensor post
  line3([133, 87, 0], [133, 87, 2.4], '#7F8FA3', 1.6); box(132.75, 86.75, 2.4, .5, .5, .5, '#F4F6F8', { edge:false });
});
// extraction hood over the belt -> hopper transfer, duct back to the filter house
add(160, () => {
  pipe3([[136.5, 82, 10.6], [136.5, 82, 13.5], [118, 75.5, 13.5], [112, 64, 13.5], [112, 62.5, 12]], .9, '#B7C3D0');
  box(135.3, 80.8, 9.2, 2.4, 2.4, 1.4, '#9AA8B8', { top:'#B9C4CF' });
  cone(136.5, 82, 9.2, 1.7, 1.1, 1.2, '#A9B5C2');
  line3([118, 75.5, 13.5], [118, 75.5, 0], '#6E7F93', 1.2); line3([124, 77.5, 13.5], [124, 77.5, 0], '#6E7F93', 1.2);
});
add(134 + 88 + 3, () => { person(131.6, 88.6, -2.4, 'tablet'); person(140.6, 86.2, -2.0, 'stand'); });

/* ---- ④ purification (PSA), compression, storage — detailed ---- */
const SPH = [[172, 54], [186, 60], [176, 74]];
const H2W = '#F1F4F7';
for (let i = 0; i < 8; i++) shCyl(142 + (i % 4) * 4, 56 + Math.floor(i / 4) * 5, 1.1, 12);
shBox(142, 70, 14, 10, 7); shBox(143, 84, 14, 7, 3.4);
SPH.forEach(([x, y]) => shCyl(x, y, 6, 14));
add(146 + 60, () => {
  box(139, 53, 0, 18, 13, .8, '#AEB9C6');
  pipe3([[141, 64.6, 1.4], [157, 64.6, 1.4]], .7, H2W);                                   // bottom header
  for (let i = 0; i < 8; i++) { const x = 142 + (i % 4) * 4, y = 56 + Math.floor(i / 4) * 5;
    cyl(x, y, .8, 1.1, 11, '#E8EDF2', { dome:.8, bands:[[2, PAL.tq, .3], [9.5, '#8C99A8', .15]] });
    pipe3([[x, y + 1.1, 1.4], [x, 64.6, 1.4]], .35, H2W); }
  pipe3([[141, 52.5, 12.6], [157, 52.5, 12.6]], .6, H2W);                                  // top (product) header
  box(141, 65.6, .8, 15, 1.6, 1.8, '#5E6B7A', { top:'#7A8796' });                           // valve skid
  for (let i = 0; i < 8; i++) { const x = 142.2 + i * 1.8; box(x, 65.9, 2.6, .8, .8, .6, '#C0392B', { edge:false, top:'#E05A4A' }); }
});
add(140 + 72 + 22, () => {
  box(142, 70, 0, 14, 10, 7, '#EEF2F6', { top:'#D6DEE6' });                                // MCC / control room
  box(142, 79.4, 5.6, 14, .6, .9, PAL.pb, { edge:false });
  windowsY(142, 80, 0, 14, 7, 1, 6, 'rgba(46,96,150,.6)');
  box(145, 72, 7, 4, 4, 1.4, '#AEBBCA');
});
// outdoor diaphragm-compressor skid
add(150 + 87 + 6, () => {
  box(143, 84, 0, 14, 7, .6, '#5E6B7A', { top:'#7A8796' });
  [[145, 85.2], [151, 85.2]].forEach(([x, y]) => {
    box(x, y, .6, 4.2, 4.6, 2.4, '#3E6A9A', { top:'#5B86B8' });                             // crankcase + motor
    hcyl(x + 4.2, x + 5.6, y + 1.2, 2.4, .7, '#C9D3DE'); hcyl(x + 4.2, x + 5.6, y + 3.4, 2.4, .7, '#C9D3DE');   // diaphragm heads
    cyl(x + 1, y + 2.3, 3, .55, 2.6, '#E3E8EE', { dome:.35 });                               // pulsation damper
  });
  box(143.2, 89.4, .6, 13.6, 1.4, 2.6, '#AEBBCA', { top:'#8796A8' });                       // aftercooler
  for (let i = 0; i < 4; i++) { ell(144.8 + i * 3.4, 90.1, 3.22, .6); g.fillStyle = '#4C5967'; g.fill(); }
  pipe3([[156.4, 86.4, 2.4], [158.5, 86.4, 2.4], [158.5, 86.4, 1.4]], .4, H2W);
});
// high-pressure manifold to the spheres: valves, pressure gauge, flanges
const HP = [[158.5, 86.4, 1.4], [166, 86.4, 1.4], [166, 74, 1.4], [170, 74, 1.4]];
add(166 + 80 + 6, () => {
  for (let y = 85; y >= 75; y -= 3.4) { line3([165.2, y, 0], [165.2, y, 1.1], '#6E7F93', 1.2); line3([166.8, y, 0], [166.8, y, 1.1], '#6E7F93', 1.2); line3([165.2, y, 1.1], [166.8, y, 1.1], '#6E7F93', 1.2); }
  pipe3(HP, .45, H2W, { gloss:.8 });
  [[162, 86.4], [166, 82.5], [166, 77.5]].forEach(([x, y]) => { const ax = x === 162 ? 'x' : 'y'; flange(x, y, 1.4, ax, .42, '#8C99A8'); });
  [[160.4, 86.4], [166, 80.2]].forEach(([x, y]) => { box(x - .35, y - .35, 1.05, .7, .7, .7, '#5E6B7A', { edge:false }); line3([x, y, 1.75], [x, y, 2.3], '#5E6B7A', 1.2); handwheel(x, y, 2.35, .32, 'z'); });
  // pressure gauge on its own post, facing the camera
  line3([163.6, 87.6, 0], [163.6, 87.6, 2.1], '#7F8FA3', 1.4);
  if (!HOLO) { const p = P(163.6, 87.6, 2.55), k = S(163.6, 87.6, 2.5), R = .42 * k;
    g.fillStyle = '#2E3B4A'; g.beginPath(); g.arc(p[0], p[1], R * 1.15, 0, 7); g.fill(); g.fillStyle = '#FFFFFF'; g.beginPath(); g.arc(p[0], p[1], R, 0, 7); g.fill();
    const arc = (a0, a1, c) => { g.strokeStyle = c; g.lineWidth = R * .2; g.beginPath(); g.arc(p[0], p[1], R * .78, a0, a1); g.stroke(); };
    const A = t => Math.PI * .75 + t * Math.PI * 1.5; arc(A(0), A(.62), '#2E9E6A'); arc(A(.62), A(.8), '#E8B42B'); arc(A(.8), A(1), '#C0392B');
    const an = A(.9); g.strokeStyle = '#16202B'; g.lineWidth = Math.max(1, R * .1); g.beginPath(); g.moveTo(p[0], p[1]); g.lineTo(p[0] + Math.cos(an) * R * .8, p[1] + Math.sin(an) * R * .8); g.stroke(); }
});
// spherical storage: legs, bracing, stair, PSV + vent stack on top
SPH.forEach(([x, y], si) => add(x + y + 4, () => {
  const legs = []; for (let a = .3; a < 6.283; a += 1.047) legs.push([x + Math.cos(a) * 4.6, y + Math.sin(a) * 4.6]);
  legs.forEach(([lx, ly], i) => { line3([lx, ly, 0], [lx, ly, 11], '#6E7F93', Math.max(1.6, .3 * S(lx, ly, 5))); const [nx, ny] = legs[(i + 1) % legs.length]; line3([lx, ly, 1], [nx, ny, 7], 'rgba(110,127,147,.6)', 1); });
  sphere(x, y, 12, 6, '#DDE4EB');
  pipe3([[x, y, 6.1], [x, y, 2], [x - 4, y + 4, 1.4]], .35, H2W);
  // PSV + vent stack
  cyl(x, y, 17.9, .35, .9, '#C0392B', { capColor:'#E05A4A' });
  pipe3([[x, y, 18.8], [x + .8, y, 19.4], [x + .8, y, 23]], .28, '#B9C4CF');
  cyl(x + .8, y, 23, .32, .25, '#8796A8');
  // top platform rail
  if (!HOLO) { const e = circ(x, y, 18.1, 1.6); g.strokeStyle = 'rgba(242,193,78,.95)'; g.lineWidth = 1; g.beginPath(); g.ellipse(e[0], e[1], e[2], e[3], 0, 0, 7); g.stroke(); }
  if (si === 2) for (let k = 0; k < 9; k++) { const a = 1.9 + k * .16, r = 6.15, z0 = 6 + k * 1.3; line3([x + Math.cos(a) * r, y + Math.sin(a) * r, z0], [x + Math.cos(a + .16) * r, y + Math.sin(a + .16) * r, z0 + 1.3], 'rgba(242,193,78,.95)', 1.2); }
  const p = P(x, y, 12); if (!HOLO) { g.fillStyle = 'rgba(27,163,156,.75)'; g.font = font(600, Math.max(7, 2.1 * S(x, y, 12))); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('H₂', p[0], p[1] + 2); }
}));
// UV/IR flame detectors
const UVIR = [[162, 79.5, 3.6], [171.5, 82.5, 3.6]];
UVIR.forEach(([x, y, h]) => add(x + y + 2, () => { line3([x, y, 0], [x, y, h], '#7F8FA3', Math.max(1.2, .14 * S(x, y, 2))); box(x - .3, y - .25, h, .6, .5, .45, '#2B3A4C', { edge:false, top:'#44566B' }); }));
add(150 + 89 + 2, () => { person(160.5, 90.2, -2.6, 'tablet'); person(168.5, 88.5, -2.2, 'stand'); });

/* ---- ⑤ hydrogen pipeline: two-tier pipe rack to the HyREX steel works (detailed) ---- */
const RACK = { x0:194.6, x1:200.4, y0:50, y1:-34, z1:5, z2:7.6, step:6 };
const H2MAIN = [[186, 60, 8.1], [197.6, 54, 8.1], [197.6, -30, 8.1], [194, -38, 8.1], [184, -38, 8.1], [181, -42, 6]];
const DETECT = [];
for (let y = RACK.y0 - 3; y >= RACK.y1; y -= RACK.step * 3) DETECT.push([RACK.x1, y]);
add(215, () => {
  const { x0, x1, y0, y1, z1, z2, step } = RACK;
  for (let y = y0; y >= y1; y -= step) {
    const lw = Math.max(1.3, .22 * S((x0 + x1) / 2, y, 4));
    line3([x0, y, 0], [x0, y, z2], '#5F7086', lw); line3([x1, y, 0], [x1, y, z2], '#5F7086', lw);
    line3([x0, y, z1], [x1, y, z1], '#5F7086', lw * .9); line3([x0, y, z2], [x1, y, z2], '#5F7086', lw * .9);
    line3([x0, y, 1.6], [x1, y, z1 - .6], 'rgba(95,112,134,.55)', lw * .5);
    if (!HOLO) { const p = P(x0, y, 0), q = P(x1, y, 0); g.fillStyle = '#BFC6CD'; g.fillRect(p[0] - lw, p[1] - lw * .6, lw * 2, lw * 1.2); g.fillRect(q[0] - lw, q[1] - lw * .6, lw * 2, lw * 1.2); }
  }
  line3([x0, y0, z2], [x0, y1, z2], '#5F7086', 1.2); line3([x1, y0, z2], [x1, y1, z2], '#5F7086', 1.2);
  line3([x0, y0, z1], [x0, y1, z1], '#5F7086', 1.1); line3([x1, y0, z1], [x1, y1, z1], '#5F7086', 1.1);
  // lower tier: utilities + cable tray
  pipe3([[195.6, y0, z1 + .45], [195.6, y1, z1 + .45]], .6, '#B7C3D0');
  pipe3([[196.8, y0, z1 + .4], [196.8, y1, z1 + .4]], .5, '#5B7FB5');
  box(198.4, y1, z1, 1.6, y0 - y1, .35, '#8E9AA7', { top:'#A9B4C0', edge:false });
  // upper tier: hydrogen main (white, turquoise identification bands) + N2 line
  pipe3(H2MAIN, 1.0, '#F4F7FA', { gloss:.8 });
  for (let y = 46; y >= -26; y -= 12) { const a = P(197.6, y, 8.1), b = P(197.6, y - .8, 8.1), k = S(197.6, y, 8.1); if (HOLO) continue; g.strokeStyle = PAL.tq; g.lineWidth = 1.05 * k; g.lineCap = 'butt'; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); }
  for (let y = 40; y >= -26; y -= 24) flange(197.6, y, 8.1, 'y', .62, '#9AA6B4');
  pipe3([[199.4, y0, z2 + .35], [199.4, y1, z2 + .35]], .4, '#C9D3DE');
  // gas (leak) detectors on the rack columns
  DETECT.forEach(([x, y]) => { box(x - .05, y - .25, 6.2, .5, .5, .55, '#F4F6F8', { edge:false }); });
  // pipe-route marker posts at ground level
  for (let y = y0 - 9; y >= y1; y -= 18) { line3([201.5, y, 0], [201.5, y, 1.1], '#E8B42B', 1.2); box(201.25, y - .25, 1.1, .5, .5, .3, '#E8B42B', { edge:false }); }
});
// hydrogen receiving station at the steel works
shBox(178, -46, 8, 7, 3.4);
add(178 - 46 + 30, () => {
  box(177.5, -46.5, 0, 9, 8, .5, '#AEB9C6');
  box(178, -46, .5, 4, 7, 3, '#EEF2F6', { top:'#D6DEE6' }); box(178, -39.4, 2.8, 4, .4, .5, PAL.tq, { edge:false });
  pipe3([[184, -38, 8.1], [184, -38, 2], [182.5, -40, 2], [182.5, -44, 2]], .55, '#F4F7FA');
  [[183.4, -41], [183.4, -44]].forEach(([x, y]) => { box(x - .3, y - .3, 1.6, .6, .6, .8, '#5E6B7A', { edge:false }); handwheel(x, y, 2.6, .3, 'z'); });
});
add(141, () => pipe3([[157, 52.5, 12.6], [160, 52.5, 6.5], [160, 70, 6.5], [170, 70, 6.5], [186, 60, 8.1]], 1.0, '#F4F7FA'));

KIND = 'env';
/* ---- HyREX steel works (background, behind the site) ---- */
shBox(100, -70, 52, 16, 20); shBox(104, -48, 34, 12, 12); shCyl(171, -51, 6.5, 56); shCyl(194, -40, 5.2, 46);
add(100 - 70 + 40, () => {
  box(100, -70, 0, 52, 16, 20, '#9FB4CA', { top:'#B9C9DA' });
  for (let i = 0; i < 7; i++) { const x = 100 + i * 52 / 7; poly3([[x, -70, 20], [x + 52 / 14, -70, 23.5], [x + 52 / 7, -70, 20], [x + 52 / 7, -54, 20], [x + 52 / 14, -54, 23.5], [x, -54, 20]], '#C3D1DF', 'rgba(80,100,125,.3)'); }
  faceY(100, -54, 0, 52, 20, () => { g.fillStyle = 'rgba(255,255,255,.35)'; for (let i = 0; i < 12; i++) g.fillRect(1.5 + i * 4.2, 12, 2.6, 4); });
  [[146, -34, 5], [156, -30, 4]].forEach(([x, y, r]) => { const p = P(x, y, 0), rx = r * S(x, y, 0); g.fillStyle = lg(p[0] - rx, 0, p[0] + rx, 0, [[0, '#4A3F3A'], [.6, '#7A6A60'], [1, '#56493F']]);
    g.beginPath(); g.moveTo(p[0] - rx, p[1]); g.quadraticCurveTo(p[0] - rx * .2, p[1] - r * 1.4 * S(x, y, 0), p[0], p[1] - r * 1.3 * S(x, y, 0)); g.quadraticCurveTo(p[0] + rx * .2, p[1] - r * 1.4 * S(x, y, 0), p[0] + rx, p[1]); g.ellipse(p[0], p[1], rx, rx * .35, 0, 0, Math.PI); g.fill(); });
});
add(104 - 48 + 22, () => { box(104, -48, 0, 34, 12, 12, '#A9BCD0', { top:'#C2D0DE' }); windowsY(104, -36, 0, 34, 12, 2, 9, 'rgba(60,90,130,.45)', 'rgba(220,235,250,.6)'); });
add(171 - 51 + 10, () => {
  frame(162, -60, 0, 18, 18, 46, 5, '#5B7FB5', 'rgba(150,165,185,.7)');
  cyl(171, -51, 0, 6.5, 54, '#C7D3E0', { dome:2.4, bands:[[18, PAL.tq, 1.2], [38, PAL.pb, .6]] });
  poly3([[138, -44, 8], [164, -52, 44], [164, -49, 44], [138, -41, 8]], '#AEBCCB');
  poly3([[138, -41, 8], [164, -49, 44], [164, -49, 47], [138, -41, 11]], '#C9D4E0');
  const b1 = P(171, -51, 57); g.fillStyle = '#FF5A4A'; g.beginPath(); g.arc(b1[0], b1[1], 2.4, 0, 7); g.fill();
});
add(194 - 40 + 8, () => { cyl(194, -40, 0, 5.2, 44, '#BCCADA', { dome:2, bands:[[16, PAL.tq, 1.1]] }); frame(188, -46, 0, 12, 12, 36, 4, '#5B7FB5', 'rgba(150,165,185,.6)'); });

KIND = 'env';
/* ---- tiny workers (scale cue) ---- */
function worker(x, y) { person(x, y, (x * 13 + y) % 6.28); }
[[46, 118], [48, 121], [90, 98], [126, 98], [160, 92], [135, 62], [80, 92], [86, 128], [88, 129], [170, 96]].forEach(([x, y]) => add(x + y + 1, () => worker(x, y)));

/* ---- floating labels (screen space) ---- */
function tag(text, wx, wy, wz, col = PAL.pb, dy = -46, dx = 0) {
  const [x0, y] = P(wx, wy, wz), x = x0 + dx;
  g.save(); g.font = font(800, 26); const w = g.measureText(text).width + 34, h = 46;
  g.strokeStyle = col; g.lineWidth = 2; g.beginPath(); g.moveTo(x0, y); g.lineTo(x, y + dy + (dy < 0 ? h / 2 : -h / 2)); g.stroke();
  g.fillStyle = col; g.beginPath(); g.arc(x0, y, 4, 0, 7); g.fill();
  g.shadowColor = 'rgba(0,40,90,.25)'; g.shadowBlur = 14; g.fillStyle = 'rgba(255,255,255,.96)';
  const bx = x - w / 2, by = y + dy - h / 2; g.beginPath(); g.roundRect(bx, by, w, h, 10); g.fill(); g.shadowBlur = 0;
  g.lineWidth = 2.5; g.stroke(); g.fillStyle = col; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, x, by + h / 2 + 1);
  g.restore();
}

