
/* ============================================================
   PLATE 03 — ② pyrolysis reactor (power loss -> backflow -> interlock)
   ============================================================ */
const CAMQ = (new URLSearchParams(location.search).get('cam') || '').split(',').map(Number);
SHOT = () => { const q = CAMQ.length === 8 ? CAMQ : [.3, .95, 122, 62, 72, 60, 19, 44];
  const T = [q[4], q[5], q[6]], dir = nrm([q[0], q[1], 0]); setCam([T[0] + dir[0] * q[2], T[1] + dir[1] * q[2], q[3]], T, q[7]); };
EXTRA_GROUND = () => { const r = rng(45);
  for (let i = 0; i < 22000; i++) { const q = unproject(r() * W, r() * H); if (!q) continue; const [x, y] = q;
    if (!(x > 0 && x < 205 && y > 0 && y < 145)) continue; const p = P(x, y, 0);
    g.fillStyle = r() > .5 ? 'rgba(90,100,110,.10)' : 'rgba(255,255,255,.12)'; g.fillRect(p[0], p[1], 1.5, 1.5); } };
EXTRA_WORLD = () => {
  g.save(); g.globalCompositeOperation = 'lighter';
  REACT.forEach(([cx, cy]) => { const [fx, fy] = facing(cx, cy, 2.75);
    [7.2, 10.6].forEach(z => { const p = P(fx, fy, z), k = S(fx, fy, z), R = 3.2 * k;
      const c = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], R); c.addColorStop(0, 'rgba(255,170,80,.42)'); c.addColorStop(.35, 'rgba(255,120,40,.12)'); c.addColorStop(1, 'rgba(255,110,40,0)');
      g.fillStyle = c; g.beginPath(); g.arc(p[0], p[1], R, 0, 7); g.fill(); }); });
  g.restore();
  // heat shimmer rising off the hot zone
  g.save(); g.strokeStyle = 'rgba(255,190,130,.35)'; g.lineWidth = 1.4;
  REACT.slice(0, 3).forEach(([cx, cy], j) => { const [fx, fy] = facing(cx, cy, 3.1);
    for (let s = -1; s <= 1; s++) { g.beginPath(); for (let z = 12; z < 22; z += .4) { const p = P(fx, fy, z), k = S(fx, fy, z); const x = p[0] + s * .8 * k + Math.sin(z * 1.7 + j + s) * .35 * k; z === 12 ? g.moveTo(x, p[1]) : g.lineTo(x, p[1]); } g.stroke(); } });
  g.restore();
};
POST = gm => {
  scrim(gm, 970);
  chevronsOn(gm, [[49.6, 48.65, 7.5], [55.5, 50, 7.5]], ACC.risk, 26, true);
  chevronsOn(gm, [[55.5, 57, 12], [55.5, 57, 28]], ACC.risk, 30, true);
  const pw = P(70, 86, 12.5); iconPowerOff(gm, pw[0], pw[1]);
  const [fx, fy] = facing(69.5, 68, 2.75), mk = P(fx, fy, 9); hudMarker(gm, mk[0], mk[1], 2);
  const tp = P(fx, fy, 12.5); readout(gm, '1,500~2,000℃', tp[0] + 8, tp[1]);
  const iv = P(43.1, 48.65, 11.6); iconShield(gm, iv[0], iv[1] - 40);
  hudTag(gm, '비상 인터록', 42.4, 48.4, 8.6, -150, 70);
  hudTag(gm, '역류 방지', 48.3, 48.65, 8.2, -230, 120);
  const t1 = facing(59, 61, 2.95); hudTag(gm, '온도 다중 감시', t1[0], t1[1], 24.2, -150, -60);
  [4.5, 9, 16].forEach(z => { const p = P(t1[0], t1[1], z + .2); gm.save(); gm.fillStyle = INK; gm.beginPath(); gm.arc(p[0], p[1], 2.5, 0, 7); gm.fill(); gm.restore(); });
  hudPanel(gm, 1300, 190, 500,
    [['위험', '초고온 · 정전 시 미반응 메탄·수소 역류', 'risk'], ['안전조치', '비상 인터록 · 역류 방지 · 온도 다중 감시', 'safe']],
    ['고압가스 안전관리법 제조허가', '산안법 PSM', '전기안전관리법'],
    { text:'메탄 열분해 전용 안전기준은 아직 없음', kind:'warn' });
  caption(gm, '② 열분해 반응기', '');
};
addEventListener('resize', render);
FONT_READY.then(render);
</script>
</body>
</html>
