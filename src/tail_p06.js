
/* ============================================================
   PLATE 06 — ⑤ pipeline to HyREX (inspection drone, leak detection)
   ============================================================ */
const CAMQ = (new URLSearchParams(location.search).get('cam') || '').split(',').map(Number);
SHOT = () => { const q = CAMQ.length === 8 ? CAMQ : [.42, .91, 115, 48, 192, -18, 8, 46];
  const T = [q[4], q[5], q[6]], dir = nrm([q[0], q[1], 0]); setCam([T[0] + dir[0] * q[2], T[1] + dir[1] * q[2], q[3]], T, q[7]); };
EXTRA_GROUND = () => { const r = rng(48);
  for (let i = 0; i < 22000; i++) { const q = unproject(r() * W, r() * H); if (!q) continue; const [x, y] = q;
    if (!(x > 0 && x < 205 && y > -80 && y < 145)) continue; const p = P(x, y, 0);
    g.fillStyle = r() > .5 ? 'rgba(90,100,110,.10)' : 'rgba(255,255,255,.12)'; g.fillRect(p[0], p[1], 1.5, 1.5); } };
const DRONE = [197.6, -1, 11.4];
function drone(x, y, z) {
  const k = S(x, y, z) * 1.6, arms = [[1, 1], [1, -1], [-1, 1], [-1, -1]];
  g.fillStyle = 'rgba(15,25,35,.25)'; const sh = P(x - 1.2, y + 2.2, 8.65); g.beginPath(); g.ellipse(sh[0], sh[1], 1.1 * k, .45 * k, 0, 0, 7); g.fill();   // shadow on the pipe tier
  arms.forEach(([sx, sy]) => line3([x, y, z], [x + sx * 1.7, y + sy * 1.7, z + .1], '#2B3A4C', Math.max(1.5, .14 * k)));
  box(x - .7, y - .9, z - .28, 1.4, 1.8, .56, '#E9EDF1', { top:'#FFFFFF' });
  box(x - .32, y + .72, z - .08, .64, .3, .22, PAL.tq, { edge:false });
  arms.forEach(([sx, sy]) => { const cx = x + sx * 1.7, cy = y + sy * 1.7; cyl(cx, cy, z, .14, .26, '#2B3A4C', { cap:'flat' });
    const e = circ(cx, cy, z + .3, 1); g.fillStyle = 'rgba(200,215,230,.35)'; g.beginPath(); g.ellipse(e[0], e[1], e[2], e[3], 0, 0, 7); g.fill(); g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 1; g.stroke(); });
  const gm = P(x, y + .15, z - .6); g.fillStyle = '#20303F'; g.beginPath(); g.arc(gm[0], gm[1], .2 * k, 0, 7); g.fill();
  g.fillStyle = 'rgba(120,210,255,.9)'; g.beginPath(); g.arc(gm[0], gm[1] + .04 * k, .08 * k, 0, 7); g.fill();
  [[-.55], [.55]].forEach(([dx]) => line3([x + dx, y - .7, z - .8], [x + dx, y + .7, z - .8], '#2B3A4C', Math.max(1, .07 * k)));
}
EXTRA_WORLD = () => {
  const [dx, dy, dz] = DRONE;
  // flight path behind the drone
  g.save(); g.setLineDash([6, 8]); g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 1.2; { const a = P(dx, 56, dz + .3), b = P(dx, dy + 1.5, dz); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); } g.restore();
  // hydrogen pulses flowing to the steel works
  g.save(); g.globalCompositeOperation = 'lighter';
  for (let y = 52; y >= -28; y -= 5.5) { if (toCam(197.6, y, 8.1)[2] < 12) continue; const p = P(197.6, y, 8.1), R = Math.min(9, .9 * S(197.6, y, 8.1));
    const c = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], R); c.addColorStop(0, 'rgba(210,250,250,.28)'); c.addColorStop(1, 'rgba(160,240,235,0)'); g.fillStyle = c; g.beginPath(); g.arc(p[0], p[1], R, 0, 7); g.fill(); }
  g.restore();
  // scan beam from the gimbal down onto the hydrogen main
  const gmb = P(dx, dy + .15, dz - .7), s0 = P(dx - 1.6, dy - 1.4, 8.6), s1 = P(dx + 1.6, dy - 1.4, 8.6), s2 = P(dx + 1.6, dy + 1.4, 8.6), s3 = P(dx - 1.6, dy + 1.4, 8.6);
  g.save(); const q = g.createLinearGradient(gmb[0], gmb[1], (s0[0] + s2[0]) / 2, (s0[1] + s2[1]) / 2); q.addColorStop(0, 'rgba(110,235,170,.38)'); q.addColorStop(1, 'rgba(110,235,170,.08)');
  g.fillStyle = q; g.beginPath(); g.moveTo(gmb[0], gmb[1]); [s0, s1, s2, s3].forEach(p => g.lineTo(p[0], p[1])); g.lineTo(s0[0], s0[1]); g.closePath(); g.fill();
  g.strokeStyle = 'rgba(140,245,190,.85)'; g.lineWidth = 1.4; g.beginPath(); [s0, s1, s2, s3].forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath(); g.stroke();
  // scanned segment of the pipe
  g.globalCompositeOperation = 'lighter'; { const a = P(197.6, dy + 1.4, 8.1), b = P(197.6, dy - 1.4, 8.1); g.strokeStyle = 'rgba(120,240,170,.75)'; g.lineWidth = 1.2 * S(197.6, dy, 8.1); g.lineCap = 'round'; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); }
  g.restore();
  drone(dx, dy, dz);
};
POST = gm => {
  scrim(gm, 970);
  DETECT.forEach(([x, y]) => { const p = P(x + .22, y, 6.5); gm.save(); gm.globalCompositeOperation = 'lighter'; const q = gm.createRadialGradient(p[0], p[1], 0, p[0], p[1], 9); q.addColorStop(0, 'rgba(120,240,170,.95)'); q.addColorStop(1, 'rgba(120,240,170,0)'); gm.fillStyle = q; gm.beginPath(); gm.arc(p[0], p[1], 9, 0, 7); gm.fill(); gm.restore(); });
  const f = P(197.6, -12, 8.1); hudMarker(gm, f[0], f[1], 5);
  hudTag(gm, '정기 검사', DRONE[0], DRONE[1], DRONE[2] + .4, -190, -60);
  hudTag(gm, '누출 감지', DETECT[3][0] + .2, DETECT[3][1], 6.5, -330, -30);
  hudTag(gm, 'HyREX 수소환원제철', 165, -51, 26, -190, -50);
  hudPanel(gm, 1300, 300, 500, [['위험', '배관 누출', 'risk'], ['안전조치', '정기 검사 · 누출 감지', 'safe']], ['고압가스법 배관 기준']);
  caption(gm, '⑤ 배관 이송', '');
};
addEventListener('resize', render);
FONT_READY.then(render);
</script>
</body>
</html>
