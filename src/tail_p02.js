
/* ============================================================
   PLATE 02 — ① feed intake & pretreatment (close drone shot + HUD)
   ============================================================ */
SHOT = () => { const T = [23, 117, 1.5], dir = nrm([.42, .91, 0]), dist = 60, hgt = 30; setCam([T[0] + dir[0] * dist, T[1] + dir[1] * dist, hgt], T, 46); };
EXTRA_GROUND = () => {                                     // concrete grain near the camera
  const r = rng(44);
  for (let i = 0; i < 26000; i++) { const q = unproject(r() * W, r() * H); if (!q) continue; const [x, y] = q;
    if (!(x > 0 && x < 205 && y > 0 && y < 145)) continue; const p = P(x, y, 0);
    g.fillStyle = r() > .5 ? 'rgba(90,100,110,.10)' : 'rgba(255,255,255,.12)'; g.fillRect(p[0], p[1], 1.5, 1.5); }
};
EXTRA_WORLD = () => {                                      // methane leak visualised as a faint cyan plume
  const r = rng(52); g.save();
  for (let i = 0; i < 46; i++) { const k = i / 46, x = 20 + Math.sin(k * 7) * .5 + k * 1.6, y = 113 + .3 + k * 1.2, z = 1.3 + k * 3.4 + r() * .3;
    const p = P(x, y, z), R = (.25 + k * 1.3) * S(x, y, z);
    const c = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], R); c.addColorStop(0, `rgba(110,220,235,${.22 * (1 - k * .6)})`); c.addColorStop(1, 'rgba(110,220,235,0)');
    g.fillStyle = c; g.beginPath(); g.arc(p[0], p[1], R, 0, 7); g.fill(); }
  for (let i = 0; i < 70; i++) { const k = r(), x = 20 + (r() - .3) * 2.4 * k, y = 113 + r() * 1.6 * k, z = 1.3 + k * 4; const p = P(x, y, z);
    g.fillStyle = `rgba(150,240,250,${.7 * (1 - k)})`; g.beginPath(); g.arc(p[0], p[1], 1.6, 0, 7); g.fill(); }
  g.restore();
};
POST = gm => {
  scrim(gm, 970);
  // detector alarm: small warm glow only
  gm.save(); gm.globalCompositeOperation = 'lighter';
  const d = P(19.5, 114.41, 2.85); let q = gm.createRadialGradient(d[0], d[1], 0, d[0], d[1], 18); q.addColorStop(0, 'rgba(255,110,90,.85)'); q.addColorStop(1, 'rgba(255,90,70,0)');
  gm.fillStyle = q; gm.beginPath(); gm.arc(d[0], d[1], 18, 0, 7); gm.fill(); gm.restore();
  const m = P(20, 113, 1.2); hudMarker(gm, m[0], m[1], 1);
  hudTag(gm, '가스검지기', 19.5, 114.2, 3.1, 'auto', -150);
  hudTag(gm, '자동 차단밸브', 18, 131.4, 2.6, 'auto', -70);
  hudTag(gm, '환기', 12.2, 116.7, 4.8, 'auto', -110);
  hudPanel(gm, 1300, 520, 500,
    [['위험', '메탄 누출 · 질식', 'risk'], ['안전조치', '가스검지기 · 환기 · 자동 차단밸브', 'safe']],
    ['도시가스사업법', '산업안전보건법 PSM']);
  caption(gm, '① 원료 인입·전처리', '');
};
addEventListener('resize', render);
FONT_READY.then(render);
</script>
</body>
</html>
