
/* ============================================================
   PLATE 04 — ③ carbon separation & storage (carbon-black dust)
   ============================================================ */
const CAMQ = (new URLSearchParams(location.search).get('cam') || '').split(',').map(Number);
SHOT = () => { const q = CAMQ.length === 8 ? CAMQ : [.4, .92, 50, 21, 138.5, 83, 6, 52];
  const T = [q[4], q[5], q[6]], dir = nrm([q[0], q[1], 0]); setCam([T[0] + dir[0] * q[2], T[1] + dir[1] * q[2], q[3]], T, q[7]); };
EXTRA_GROUND = () => { const r = rng(46);
  for (let i = 0; i < 22000; i++) { const q = unproject(r() * W, r() * H); if (!q) continue; const [x, y] = q;
    if (!(x > 0 && x < 205 && y > 0 && y < 145)) continue; const p = P(x, y, 0);
    g.fillStyle = r() > .5 ? 'rgba(90,100,110,.10)' : 'rgba(255,255,255,.12)'; g.fillRect(p[0], p[1], 1.5, 1.5); }
  // carbon-black fines settled on the floor round the station
  const r2 = rng(61);
  for (let i = 0; i < 900; i++) { const a = r2() * 6.283, d = Math.pow(r2(), .6) * 5, x = 136.5 + Math.cos(a) * d * 1.3, y = 83.5 + Math.sin(a) * d; const p = P(x, y, .02);
    g.fillStyle = `rgba(25,28,32,${.12 + r2() * .2})`; g.fillRect(p[0], p[1], 2, 1.4); }
};
const ZONE = [131, 78, 0, 11, 9, 9.5];     // explosion-protected (dust) zone volume: x, y, z, w, d, h
EXTRA_WORLD = () => {
  // airborne carbon-black dust round the belt head and the hopper inlet
  const r = rng(71);
  g.save();
  for (let i = 0; i < 70; i++) { const x = 136.5 + (r() - .5) * 8, y = 82 + (r() - .5) * 6, z = 5.5 + r() * 4.5, p = P(x, y, z), R = (1.4 + r() * 2.2) * S(x, y, z);
    const c = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], R); c.addColorStop(0, 'rgba(48,50,56,.10)'); c.addColorStop(1, 'rgba(38,40,46,0)'); g.fillStyle = c; g.beginPath(); g.arc(p[0], p[1], R, 0, 7); g.fill(); }
  for (let i = 0; i < 150; i++) { const x = 136.5 + (r() - .5) * 8, y = 82 + (r() - .5) * 6, z = 5 + r() * 5, p = P(x, y, z);
    g.fillStyle = `rgba(20,22,26,${.25 + r() * .45})`; g.beginPath(); g.arc(p[0], p[1], .6 + r() * 1.3, 0, 7); g.fill(); }
  // particles drawn into the hood (streaks toward the hood mouth)
  const hm = P(136.5, 82, 8.3);
  for (let i = 0; i < 26; i++) { const a = r() * 6.283, d = 1.2 + r() * 1.6, x = 136.5 + Math.cos(a) * d, y = 82 + Math.sin(a) * d, z = 6.8 + r() * 1.2, p = P(x, y, z);
    const q = [p[0] + (hm[0] - p[0]) * .55, p[1] + (hm[1] - p[1]) * .55]; const gr = g.createLinearGradient(p[0], p[1], q[0], q[1]);
    gr.addColorStop(0, 'rgba(30,32,36,0)'); gr.addColorStop(1, 'rgba(30,32,36,.55)'); g.strokeStyle = gr; g.lineWidth = 1.4; g.beginPath(); g.moveTo(p[0], p[1]); g.lineTo(q[0], q[1]); g.stroke(); }
  g.restore();
  // static spark at the belt head pulley
  const sp = P(136.3, 83.1, 7.0);
  g.save(); g.globalCompositeOperation = 'lighter';
  let c = g.createRadialGradient(sp[0], sp[1], 0, sp[0], sp[1], 26); c.addColorStop(0, 'rgba(255,240,190,.95)'); c.addColorStop(.25, 'rgba(255,190,90,.45)'); c.addColorStop(1, 'rgba(255,160,60,0)');
  g.fillStyle = c; g.beginPath(); g.arc(sp[0], sp[1], 26, 0, 7); g.fill();
  g.strokeStyle = 'rgba(255,245,210,.95)'; g.lineWidth = 1.4; const rs = rng(5);
  for (let k = 0; k < 6; k++) { let x = sp[0], y = sp[1]; const an = rs() * 6.283; g.beginPath(); g.moveTo(x, y); for (let s = 0; s < 4; s++) { x += Math.cos(an + (rs() - .5)) * 5; y += Math.sin(an + (rs() - .5)) * 5; g.lineTo(x, y); } g.stroke(); }
  g.restore();
  // explosion-protected zone: dashed volume outline
  const [zx, zy, zz, zw, zd, zh] = ZONE, Z = [[zx, zy], [zx + zw, zy], [zx + zw, zy + zd], [zx, zy + zd]];
  g.save(); g.setLineDash([9, 7]); g.strokeStyle = 'rgba(255,170,90,.9)'; g.lineWidth = 1.6;
  [zz, zz + zh].forEach(z => { const pts = Z.map(([x, y]) => P(x, y, z)); g.beginPath(); pts.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath(); g.stroke(); });
  Z.forEach(([x, y]) => { const a = P(x, y, zz), b = P(x, y, zz + zh); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); });
  g.setLineDash([]); g.fillStyle = 'rgba(255,170,90,.07)'; const fl = Z.map(([x, y]) => P(x, y, .03)); g.beginPath(); fl.forEach((p, i) => i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])); g.closePath(); g.fill();
  g.restore();
};
POST = gm => {
  scrim(gm, 970);
  const m = P(136.4, 82.6, 7.3); hudMarker(gm, m[0], m[1], 3);
  hudTag(gm, '집진 설비', 136.5, 82, 10.4, -170, -90);
  hudTag(gm, '접지', 114 + 3.1, 82 + 3, .7, -120, 70);
  hudTag(gm, '분진 농도 감시', 133, 87, 2.9, -150, 130);
  hudTag(gm, '방폭', ZONE[0] + ZONE[3], ZONE[1] + ZONE[4], 0, 90, 70);
  hudPanel(gm, 1300, 210, 500,
    [['위험', '카본블랙 분진 폭발 · 정전기 착화', 'risk'], ['안전조치', '집진·방폭 설비 · 접지 · 분진 농도 감시', 'safe']],
    ['산업안전보건기준 규칙(분진)', 'KCs 방폭', '화평법'],
    { text:'청록수소 고유 위험', kind:'tq' });
  caption(gm, '③ 탄소 분리·저장', '');
};
addEventListener('resize', render);
FONT_READY.then(render);
</script>
</body>
</html>
