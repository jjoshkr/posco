
/* ============================================================
   PLATE 05 — ④ purification, compression & storage (invisible H2 flame)
   ============================================================ */
const CAMQ = (new URLSearchParams(location.search).get('cam') || '').split(',').map(Number);
SHOT = () => { const q = CAMQ.length === 8 ? CAMQ : [.35, .94, 52, 20, 162, 79, 6, 54];
  const T = [q[4], q[5], q[6]], dir = nrm([q[0], q[1], 0]); setCam([T[0] + dir[0] * q[2], T[1] + dir[1] * q[2], q[3]], T, q[7]); };
EXTRA_GROUND = () => { const r = rng(47);
  for (let i = 0; i < 22000; i++) { const q = unproject(r() * W, r() * H); if (!q) continue; const [x, y] = q;
    if (!(x > 0 && x < 205 && y > 0 && y < 145)) continue; const p = P(x, y, 0);
    g.fillStyle = r() > .5 ? 'rgba(90,100,110,.10)' : 'rgba(255,255,255,.12)'; g.fillRect(p[0], p[1], 1.5, 1.5); } };
const LEAK = [166, 82.5, 1.4];
const ZONE5 = [142.5, 83, 0, 26.5, 9.5, 6];
EXTRA_WORLD = () => {
  const [lx, ly, lz] = LEAK;
  // UV/IR detection cones aimed at the leak
  UVIR.forEach(([x, y, h]) => { const a = P(x, y, h + .2), b = P(lx, ly, lz + 1.2), dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L, w = L * .32;
    g.save(); const q = g.createLinearGradient(a[0], a[1], b[0], b[1]); q.addColorStop(0, 'rgba(255,190,120,.30)'); q.addColorStop(1, 'rgba(255,190,120,.04)');
    g.fillStyle = q; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0] + nx * w, b[1] + ny * w); g.lineTo(b[0] - nx * w, b[1] - ny * w); g.closePath(); g.fill();
    g.strokeStyle = 'rgba(255,200,140,.45)'; g.lineWidth = 1; g.setLineDash([4, 5]); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0] + nx * w, b[1] + ny * w); g.moveTo(a[0], a[1]); g.lineTo(b[0] - nx * w, b[1] - ny * w); g.stroke(); g.restore(); });
  // near-invisible hydrogen flame: a pale blue tint and heat ripple rising from the flange
  g.save(); g.globalCompositeOperation = 'lighter';
  for (let i = 0; i < 18; i++) { const k = i / 18, p = P(lx + Math.sin(k * 5) * .15, ly, lz + .2 + k * 3), R = (.35 + k * .7) * S(lx, ly, lz + k * 3);
    const c = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], R); c.addColorStop(0, `rgba(150,200,255,${.07 * (1 - k)})`); c.addColorStop(1, 'rgba(150,200,255,0)'); g.fillStyle = c; g.beginPath(); g.arc(p[0], p[1], R, 0, 7); g.fill(); }
  g.restore();
  g.save(); g.strokeStyle = 'rgba(235,245,255,.42)'; g.lineWidth = 1.2;
  for (let s = -2; s <= 2; s++) { g.beginPath(); for (let z = 0; z < 3.6; z += .08) { const p = P(lx, ly, lz + .3 + z), k = S(lx, ly, lz + z); const x = p[0] + s * .22 * k + Math.sin(z * 4.2 + s * 1.3) * .14 * k * (1 + z * .3); z === 0 ? g.moveTo(x, p[1]) : g.lineTo(x, p[1]); } g.stroke(); }
  g.restore();
  // explosion-protected zone round the compressor skid and manifold
  const [zx, zy, zz, zw, zd, zh] = ZONE5, Z = [[zx, zy], [zx + zw, zy], [zx + zw, zy + zd], [zx, zy + zd]];
  g.save(); g.setLineDash([9, 7]); g.strokeStyle = 'rgba(255,170,90,.85)'; g.lineWidth = 1.5;
  [zz, zz + zh].forEach(z => { const pts = Z.map(([x, y]) => P(x, y, z)); g.beginPath(); pts.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath(); g.stroke(); });
  Z.forEach(([x, y]) => { const a = P(x, y, zz), b = P(x, y, zz + zh); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); });
  g.setLineDash([]); g.fillStyle = 'rgba(255,170,90,.06)'; const fl = Z.map(([x, y]) => P(x, y, .03)); g.beginPath(); fl.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath(); g.fill();
  g.restore();
};
POST = gm => {
  scrimL(gm, 900);
  // detector status lamps
  UVIR.forEach(([x, y, h]) => { const p = P(x, y + .26, h + .22); gm.save(); gm.globalCompositeOperation = 'lighter'; const q = gm.createRadialGradient(p[0], p[1], 0, p[0], p[1], 14);
    q.addColorStop(0, 'rgba(255,170,90,.9)'); q.addColorStop(1, 'rgba(255,150,70,0)'); gm.fillStyle = q; gm.beginPath(); gm.arc(p[0], p[1], 14, 0, 7); gm.fill(); gm.restore(); });
  const m = P(LEAK[0], LEAK[1], LEAK[2]); hudMarker(gm, m[0], m[1], 4);
  hudTag(gm, 'UV/IR 화염검지', UVIR[1][0], UVIR[1][1], UVIR[1][2] + .5, 140, 90);
  hudTag(gm, '안전밸브', 176, 74, 18.6, 130, -40);
  hudTag(gm, '고압', 163.6, 87.6, 2.9, -40, 130);
  hudTag(gm, '방폭 구역', ZONE5[0] + ZONE5[3], ZONE5[1], ZONE5[5], 120, -20);
  hudPanel(gm, 150, 230, 520,
    [['위험', '고압 · 눈에 잘 안 보이는 수소 불꽃 · 수소취성', 'risk'], ['안전조치', 'UV/IR 화염검지 · 안전밸브 · 방폭 구역', 'safe']],
    ['고압가스법 KGS 검사', '산안법 PSM']);
  caption(gm, '④ 수소 정제·압축·저장', '');
};
addEventListener('resize', render);
FONT_READY.then(render);
</script>
</body>
</html>
