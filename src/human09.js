/* ---------- semi-realistic worker figure (front view, backlit) ----------
   units: 1 = one head height; figure is ~7.6 heads tall. Drawn into its own layer, then graded. */
const LOOKS = [
  { skin:'#E0B48E', hair:'#1E1612', build:1.00 }, { skin:'#D4A27C', hair:'#2A1D15', build:1.07 }, { skin:'#E6BC98', hair:'#15100D', build:.96 },
  { skin:'#D8AA84', hair:'#231912', build:1.04 }, { skin:'#DDB08B', hair:'#18120E', build:.98 }, { skin:'#CF9F78', hair:'#2B2018', build:1.05 } ];
function poseJoints(pose) {
  const J = { sL:[-.96, 6.3], sR:[.96, 6.3], hL:[-.47, 3.92], hR:[.47, 3.92], kL:[-.5, 2.08], kR:[.52, 2.1], aL:[-.58, .42], aR:[.62, .42],
    eL:[-1.18, 4.98], wL:[-1.22, 3.92], eR:[1.18, 4.98], wR:[1.22, 3.92], tilt:0, handL:'open', handR:'open' };
  const up = (s) => { J['e' + s] = [s === 'L' ? -1.5 : 1.5, 7.55]; J['w' + s] = [s === 'L' ? -1.72 : 1.72, 8.86]; };
  if (pose === 'cheer') { up('L'); up('R'); J.tilt = -.06; }
  if (pose === 'jump') { up('L'); up('R'); J.kL = [-.78, 2.25]; J.kR = [.78, 2.25]; J.aL = [-.58, .6]; J.aR = [.58, .6]; J.tilt = -.08; }
  if (pose === 'fist') { J.eR = [1.32, 7.6]; J.wR = [1.12, 8.92]; J.handR = 'fist'; J.eL = [-1.32, 5.05]; J.wL = [-.72, 5.62]; J.handL = 'fist'; J.tilt = .05; }
  if (pose === 'helmet') { J.eR = [1.38, 7.7]; J.wR = [1.22, 9.02]; J.handR = 'grip'; J.tilt = -.04; }
  if (pose === 'five') { J.eR = [1.6, 7.25]; J.wR = [2.12, 8.32]; J.tilt = .07; }
  return J;
}
function hseg(A, B, ra, rb, base, bulge = 0) {                 // tapered, slightly muscled capsule, shaded across its width
  const dx = B[0] - A[0], dy = B[1] - A[1], L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L, an = Math.atan2(dy, dx);
  const M = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2], rm = (ra + rb) / 2 * (1 + bulge), c = 2 * rm - (ra + rb) / 2;
  g.beginPath(); g.moveTo(A[0] + nx * ra, A[1] + ny * ra);
  g.quadraticCurveTo(M[0] + nx * c, M[1] + ny * c, B[0] + nx * rb, B[1] + ny * rb);
  g.arc(B[0], B[1], rb, an + Math.PI / 2, an - Math.PI / 2, true);
  g.quadraticCurveTo(M[0] - nx * c, M[1] - ny * c, A[0] - nx * ra, A[1] - ny * ra);
  g.arc(A[0], A[1], ra, an - Math.PI / 2, an + Math.PI / 2, true); g.closePath();
  const R = Math.max(ra, rb) * 1.05, q = g.createLinearGradient(M[0] + nx * R, M[1] + ny * R, M[0] - nx * R, M[1] - ny * R);
  q.addColorStop(0, shade(base, .5)); q.addColorStop(.12, shade(base, .1)); q.addColorStop(.5, base); q.addColorStop(.88, shade(base, -.3)); q.addColorStop(1, shade(base, .18));
  g.fillStyle = q; g.fill();
  return { A, B, nx, ny, ra, rb };
}
function bandOn(s, t, w, col) {                               // reflective band across a limb, clipped to it
  g.save(); g.clip(); const x = s.A[0] + (s.B[0] - s.A[0]) * t, y = s.A[1] + (s.B[1] - s.A[1]) * t, r = Math.max(s.ra, s.rb) * 1.4;
  g.strokeStyle = col; g.lineWidth = w; g.beginPath(); g.moveTo(x + s.nx * r, y + s.ny * r); g.lineTo(x - s.nx * r, y - s.ny * r); g.stroke(); g.restore();
}
function human(fx, fy, hu, pose, look, flip = 1) {
  const lift = pose === 'jump' ? .6 : 0, bw = look.build;
  const X = x => fx + x * hu * flip * bw, Y = y => fy - (y + lift) * hu, Q = p => [X(p[0]), Y(p[1])];
  const J = poseJoints(pose);
  const upperArms = () => { const ua = (sh, e) => { const u2 = hseg(Q(sh), Q(e), .33 * hu * bw, .25 * hu, '#24508C', .08); bandOn(u2, .6, .15 * hu, '#D9DCD6'); }; ua(J.sL, J.eL); ua(J.sR, J.eR); };
  const JACK = '#24508C', PANT = '#1A2A44', REFL = '#D9DCD6', GLOVE = '#D6D2C6', BOOT = '#1C1E22';
  // ---- legs (trousers) + boots
  const leg = (h, k, a) => { const t = hseg(Q(h), Q(k), .45 * hu, .31 * hu, PANT, .1); const s = hseg(Q(k), Q(a), .31 * hu, .25 * hu, PANT, .06); bandOn(s, .32, .16 * hu, REFL);
    g.strokeStyle = 'rgba(0,0,0,.25)'; g.lineWidth = .05 * hu; g.beginPath(); const kk = Q(k); g.moveTo(kk[0] - .15 * hu, kk[1] - .05 * hu); g.quadraticCurveTo(kk[0], kk[1] + .08 * hu, kk[0] + .15 * hu, kk[1] - .02 * hu); g.stroke(); };
  leg(J.hL, J.kL, J.aL); leg(J.hR, J.kR, J.aR);
  [J.aL, J.aR].forEach((a, i) => { const p = Q(a), s = i ? 1 : -1;
    g.fillStyle = BOOT; g.beginPath(); g.moveTo(p[0] - .28 * hu, p[1] - .14 * hu); g.lineTo(p[0] + .28 * hu, p[1] - .14 * hu); g.lineTo(p[0] + .33 * hu, p[1] + .3 * hu);
    g.quadraticCurveTo(p[0] + s * .08 * hu, p[1] + .5 * hu, p[0] - .33 * hu, p[1] + .3 * hu); g.closePath(); g.fill();
    g.fillStyle = 'rgba(255,255,255,.18)'; g.beginPath(); g.ellipse(p[0] - .06 * hu, p[1] + .22 * hu, .1 * hu, .05 * hu, 0, 0, 7); g.fill();
    g.fillStyle = '#0E0F11'; g.fillRect(p[0] - .34 * hu, p[1] + .36 * hu, .68 * hu, .09 * hu); });
  // pelvis
  g.fillStyle = PANT; g.beginPath(); [[-.76, 4.05], [.76, 4.05], [.62, 3.3], [0, 3.22], [-.62, 3.3]].forEach((p, i) => { const q = Q(p); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); }); g.closePath(); g.fill();
  upperArms();
  // ---- jacket torso
  const T = [[-.24, 6.78], [-.78, 6.56], [-1.07, 6.22], [-1.0, 5.6], [-.88, 4.6], [-.9, 3.66], [0, 3.58], [.9, 3.66], [.88, 4.6], [1.0, 5.6], [1.07, 6.22], [.78, 6.56], [.24, 6.78]];
  const torso = () => { g.beginPath(); T.forEach((p, i) => { const q = Q(p); if (!i) g.moveTo(q[0], q[1]); else { const pr = Q(T[i - 1]); g.quadraticCurveTo(pr[0], pr[1], (pr[0] + q[0]) / 2, (pr[1] + q[1]) / 2); } }); const e = Q(T[T.length - 1]); g.lineTo(e[0], e[1]); g.closePath(); };
  torso(); { const l = Q([-1.05, 5]), r = Q([1.05, 5]), q = g.createLinearGradient(l[0], 0, r[0], 0);
    q.addColorStop(0, shade(JACK, .45)); q.addColorStop(.1, shade(JACK, .08)); q.addColorStop(.55, JACK); q.addColorStop(.9, shade(JACK, -.32)); q.addColorStop(1, shade(JACK, .15)); g.fillStyle = q; g.fill(); }
  g.save(); torso(); g.clip();
  [[5.3, .17], [4.62, .17]].forEach(([y, w]) => { const a = Q([-1.2, y]), b = Q([1.2, y]); g.strokeStyle = REFL; g.lineWidth = w * hu; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); });
  const z0 = Q([0, 6.5]), z1 = Q([0, 3.62]); g.strokeStyle = 'rgba(0,0,0,.35)'; g.lineWidth = .05 * hu; g.beginPath(); g.moveTo(z0[0], z0[1]); g.lineTo(z1[0], z1[1]); g.stroke();
  [[-.55, 5.95], [.35, 5.95]].forEach(p => { const q = Q(p); g.strokeStyle = 'rgba(0,0,0,.22)'; g.lineWidth = .035 * hu; g.strokeRect(Math.min(q[0], q[0] + .32 * hu * flip * bw), q[1] - .3 * hu, .32 * hu * bw, .3 * hu); });
  g.fillStyle = 'rgba(0,0,0,.18)'; const hm = Q([-.84, 3.86]); g.fillRect(hm[0] - (flip < 0 ? 1.68 * hu * bw : 0), hm[1], 1.68 * hu * bw, .12 * hu);
  g.restore();
  // collar
  g.fillStyle = shade(JACK, -.15); [[-1, 1]].forEach(() => { [-1, 1].forEach(s => { const a = Q([s * .08, 6.84]), b = Q([s * .44, 6.68]), c = Q([s * .18, 6.3]); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.lineTo(c[0], c[1]); g.closePath(); g.fill(); }); });
  // ---- neck + head
  const head = () => {
    const nk = hseg(Q([0, 6.62]), Q([0, 6.86]), .19 * hu, .18 * hu, shade(look.skin, -.18));
    g.fillStyle = 'rgba(40,25,15,.35)'; const ch = Q([0, 6.78]); g.beginPath(); g.ellipse(ch[0], ch[1], .17 * hu, .06 * hu, 0, 0, 7); g.fill();
    const c = Q([0, 7.24]);
    g.save(); g.translate(c[0], c[1]); g.rotate(J.tilt * flip); g.translate(-c[0], -c[1]);
    [-1, 1].forEach(s => { const e = Q([s * .37, 7.2]); g.fillStyle = shade(look.skin, -.08); g.beginPath(); g.ellipse(e[0], e[1], .07 * hu, .12 * hu, 0, 0, 7); g.fill(); });
    // face shape: wider cranium, narrower jaw
    g.beginPath(); const P0 = Q([0, 7.72]), Lt = Q([-.37, 7.35]), Lj = Q([-.3, 6.92]), Ch = Q([0, 6.74]), Rj = Q([.3, 6.92]), Rt = Q([.37, 7.35]);
    g.moveTo(P0[0], P0[1]); g.quadraticCurveTo(Lt[0] - .02 * hu * flip, P0[1], Lt[0], Lt[1]); g.quadraticCurveTo(Lt[0], Lj[1], Lj[0], Lj[1]); g.quadraticCurveTo(Ch[0] - .17 * hu * flip, Ch[1], Ch[0], Ch[1]);
    g.quadraticCurveTo(Ch[0] + .17 * hu * flip, Ch[1], Rj[0], Rj[1]); g.quadraticCurveTo(Rt[0], Rj[1], Rt[0], Rt[1]); g.quadraticCurveTo(Rt[0], P0[1], P0[0], P0[1]); g.closePath();
    { const l = Q([-.4, 7.2]), r = Q([.4, 7.2]), q = g.createLinearGradient(l[0], 0, r[0], 0); q.addColorStop(0, shade(look.skin, .38)); q.addColorStop(.18, look.skin); q.addColorStop(.7, shade(look.skin, -.1)); q.addColorStop(1, shade(look.skin, -.28)); g.fillStyle = q; g.fill(); }
    if (hu > 14) {
      const F = (x, y) => Q([x, y]);
      g.fillStyle = 'rgba(160,80,60,.18)'; [-1, 1].forEach(s => { const p = F(s * .2, 7.04); g.beginPath(); g.ellipse(p[0], p[1], .08 * hu, .05 * hu, 0, 0, 7); g.fill(); });
      g.strokeStyle = look.hair; g.lineWidth = .045 * hu; g.lineCap = 'round';
      [-1, 1].forEach(s => { const a = F(s * .08, 7.38), b = F(s * .25, 7.41); g.beginPath(); g.moveTo(a[0], a[1]); g.quadraticCurveTo((a[0] + b[0]) / 2, a[1] - .05 * hu, b[0], b[1]); g.stroke(); });
      [-1, 1].forEach(s => { const e = F(s * .155, 7.27); g.fillStyle = '#F4EEE8'; g.beginPath(); g.ellipse(e[0], e[1], .078 * hu, .045 * hu, 0, 0, 7); g.fill();
        g.fillStyle = '#2A1C14'; g.beginPath(); g.arc(e[0] + s * .005 * hu, e[1], .036 * hu, 0, 7); g.fill();
        g.strokeStyle = 'rgba(40,25,15,.7)'; g.lineWidth = .02 * hu; g.beginPath(); g.ellipse(e[0], e[1] + .005 * hu, .065 * hu, .035 * hu, 0, Math.PI * 1.05, Math.PI * 1.95); g.stroke(); });
      g.strokeStyle = 'rgba(90,50,30,.45)'; g.lineWidth = .03 * hu; { const a = F(.02, 7.24), b = F(.05, 7.08), c2 = F(-.06, 7.06); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.lineTo(c2[0], c2[1]); g.stroke(); }
      // open smile
      const m0 = F(-.13, 6.97), m1 = F(.13, 6.97), mb = F(0, 6.86);
      g.fillStyle = '#5A2420'; g.beginPath(); g.moveTo(m0[0], m0[1]); g.quadraticCurveTo(mb[0], m0[1] - .015 * hu, m1[0], m1[1]); g.quadraticCurveTo(mb[0], mb[1] + .03 * hu, m0[0], m0[1]); g.fill();
      g.fillStyle = '#F2EEE6'; g.beginPath(); g.moveTo(m0[0] + .02 * hu, m0[1] + .005 * hu); g.quadraticCurveTo(mb[0], m0[1] - .01 * hu, m1[0] - .02 * hu, m1[1] + .005 * hu); g.lineTo(m1[0] - .04 * hu, m1[1] + .035 * hu); g.lineTo(m0[0] + .04 * hu, m0[1] + .035 * hu); g.closePath(); g.fill();
    }
    // hair at the temples, helmet (or bare head when the helmet is held up)
    g.fillStyle = look.hair; [-1, 1].forEach(s => { const a = Q([s * .36, 7.5]), b = Q([s * .38, 7.24]), c2 = Q([s * .3, 7.3]); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.lineTo(c2[0], c2[1]); g.closePath(); g.fill(); });
    if (pose === 'helmet') { const t = Q([0, 7.5]); g.beginPath(); g.ellipse(t[0], t[1], .39 * hu * bw, .26 * hu, 0, Math.PI, 0); g.lineTo(t[0] + .39 * hu * bw, t[1] + .05 * hu); g.lineTo(t[0] - .39 * hu * bw, t[1] + .05 * hu); g.closePath(); g.fill(); }
    else drawHelmet(Q([0, 7.47]), hu * bw, 0);
    g.restore();
  };
  // ---- arms: upper arm drawn behind the jacket body, forearm + hand in front
  const upper = (sh, e) => { const ua = hseg(Q(sh), Q(e), .33 * hu * bw, .25 * hu, JACK, .08); bandOn(ua, .6, .15 * hu, REFL); };
  const lower = (s0, e, w, hand) => {
    const el = Q(e), wr = Q(w);
    hseg(el, wr, .25 * hu, .2 * hu, JACK, .05);
    hseg([wr[0] - (wr[0] - el[0]) * .14, wr[1] - (wr[1] - el[1]) * .14], wr, .21 * hu, .2 * hu, shade(JACK, -.35));
    g.strokeStyle = 'rgba(0,0,0,.22)'; g.lineWidth = .04 * hu; g.beginPath(); g.moveTo(el[0] - .12 * hu, el[1] + .04 * hu); g.quadraticCurveTo(el[0], el[1] - .06 * hu, el[0] + .12 * hu, el[1] + .04 * hu); g.stroke();
    const dx = wr[0] - el[0], dy = wr[1] - el[1], L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L;
    const len = hand === 'fist' ? .3 : .58, tip = [wr[0] + ux * len * hu, wr[1] + uy * len * hu];
    const side = (s0[0] < 0 ? -1 : 1) * flip, nx = -uy * side, ny = ux * side;
    hseg(wr, tip, .19 * hu, hand === 'fist' ? .2 * hu : .16 * hu, GLOVE);
    hseg([wr[0] + nx * .14 * hu + ux * .1 * hu, wr[1] + ny * .14 * hu + uy * .1 * hu], [wr[0] + nx * .27 * hu + ux * .3 * hu, wr[1] + ny * .27 * hu + uy * .3 * hu], .07 * hu, .06 * hu, shade(GLOVE, -.08));
    if (hand === 'open') { g.strokeStyle = 'rgba(0,0,0,.22)'; g.lineWidth = .025 * hu; for (let k = -1; k <= 1; k++) { const a = [tip[0] - ux * .2 * hu + nx * k * .07 * hu, tip[1] - uy * .2 * hu + ny * k * .07 * hu]; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(tip[0] + nx * k * .07 * hu + ux * .02 * hu, tip[1] + ny * k * .07 * hu + uy * .02 * hu); g.stroke(); } }
    if (hand === 'grip') drawHelmet([tip[0] + ux * .05 * hu, tip[1] + uy * .3 * hu], hu * bw, .35 * flip);
  };
  head();
  lower(J.sL, J.eL, J.wL, J.handL); lower(J.sR, J.eR, J.wR, J.handR);
}
function drawHelmet(c, hu, rot) {
  g.save(); g.translate(c[0], c[1]); g.rotate(rot);
  let q = g.createLinearGradient(-.45 * hu, 0, .45 * hu, 0); q.addColorStop(0, '#FFFFFF'); q.addColorStop(.6, '#ECECE8'); q.addColorStop(1, '#BDBDB8');
  g.fillStyle = q; g.beginPath(); g.ellipse(0, 0, .44 * hu, .38 * hu, 0, Math.PI, 0); g.closePath(); g.fill();
  g.strokeStyle = 'rgba(0,0,0,.12)'; g.lineWidth = .03 * hu; g.beginPath(); g.moveTo(0, -.38 * hu); g.lineTo(0, 0); g.stroke();
  g.fillStyle = '#E2E2DD'; g.beginPath(); g.ellipse(0, .01 * hu, .52 * hu, .075 * hu, 0, 0, 7); g.fill();
  g.fillStyle = 'rgba(0,0,0,.22)'; g.beginPath(); g.ellipse(0, .05 * hu, .5 * hu, .05 * hu, 0, 0, Math.PI); g.fill();
  g.fillStyle = '#1BA39C'; g.fillRect(-.07 * hu, -.24 * hu, .14 * hu, .16 * hu);
  g.restore();
}
function crewman(x, y, pose, i = 0, flip = 1) {
  const f = P(x, y, 0), hu = S(x, y, 1) * 1.76 / 7.6, look = LOOKS[i % LOOKS.length];
  // contact shadow cast toward the camera (sun behind the crew)
  const lift = pose === 'jump' ? .6 : 0;
  g.save(); g.filter = 'blur(6px)'; g.fillStyle = `rgba(15,25,15,${pose === 'jump' ? .25 : .38})`; g.beginPath(); g.ellipse(f[0] + .5 * hu, f[1] + .35 * hu, 1.25 * hu, .3 * hu, .06, 0, 7); g.fill(); g.restore();
  // draw the person on its own layer so it can be graded as one object
  const c = document.createElement('canvas'); c.width = g.canvas.width; c.height = g.canvas.height;
  const pg = c.getContext('2d'); pg.setTransform(DPR, 0, 0, DPR, 0, 0);
  const keep = g; g = pg; human(f[0], f[1], hu, pose, look, flip);
  // backlight grade: warm top, cooler shadowed lower body
  g.globalCompositeOperation = 'source-atop';
  const top = f[1] - (7.8 + lift) * hu, q = g.createLinearGradient(0, top, 0, f[1]); q.addColorStop(0, 'rgba(255,214,160,.16)'); q.addColorStop(.5, 'rgba(0,0,0,0)'); q.addColorStop(1, 'rgba(10,20,35,.22)');
  g.fillStyle = q; g.fillRect(f[0] - 4 * hu, top, 8 * hu, 8.5 * hu); g = keep;
  g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(c, 0, 0); g.restore();
}
