
/* ============================================================
   PLATE 07 — all five points cleared, permit gates passed (wide)
   ============================================================ */
const CAMQ = (new URLSearchParams(location.search).get('cam') || '').split(',').map(Number);
SHOT = () => { const q = CAMQ.length === 8 ? CAMQ : [.5, .87, 330, 105, 104, 28, 0, 52];
  const T = [q[4], q[5], q[6]], dir = nrm([q[0], q[1], 0]); setCam([T[0] + dir[0] * q[2], T[1] + dir[1] * q[2], q[3]], T, q[7]); };
const POINTS = [[1, 25, 113, 9], [2, 66, 62, 44], [3, 122, 82, 40], [4, 178, 66, 22], [5, 197.6, 8, 20]];
const GATES = ['통합환경허가', 'KGS 완성검사', '산안법 PSM 심사', '소방·방폭', '인허가 로드맵'];
function okMarker(gg, sx, sy, n) {
  gg.save(); gg.shadowColor = 'rgba(0,10,20,.55)'; gg.shadowBlur = 8;
  gg.fillStyle = 'rgba(4,14,24,.62)'; gg.beginPath(); gg.arc(sx, sy, 17, 0, 7); gg.fill();
  gg.strokeStyle = ACC.safe; gg.lineWidth = 1.6; gg.beginPath(); gg.arc(sx, sy, 17, 0, 7); gg.stroke();
  gg.lineWidth = 2; gg.beginPath(); gg.moveTo(sx - 7, sy); gg.lineTo(sx - 2, sy + 5); gg.lineTo(sx + 8, sy - 6); gg.stroke();
  gg.lineWidth = 1; gg.strokeStyle = 'rgba(142,224,188,.7)'; gg.beginPath(); gg.moveTo(sx, sy + 17); gg.lineTo(sx, sy + 44); gg.stroke();
  gg.restore();
  txt(gg, String(n).padStart(2, '0'), sx + 25, sy + 8, 22, 600, ACC.safe);
}
POST = gm => {
  // soft top-of-frame vignette is already in grade(); add a bottom band for the gate timeline
  let q = gm.createLinearGradient(0, H - 470, 0, H); q.addColorStop(0, 'rgba(4,12,22,0)'); q.addColorStop(.45, 'rgba(4,12,22,.58)'); q.addColorStop(1, 'rgba(4,12,22,.78)');
  gm.fillStyle = q; gm.fillRect(0, H - 470, W, 470);
  POINTS.forEach(([n, x, y, z]) => { const p = P(x, y, z); okMarker(gm, p[0], p[1] - 44, n); });
  // gate timeline: hairline with five check nodes
  const x0 = 150, x1 = W - 150, yL = 800, step = (x1 - x0) / (GATES.length - 1);
  gm.save(); gm.strokeStyle = 'rgba(255,255,255,.35)'; gm.lineWidth = 1; gm.beginPath(); gm.moveTo(x0 - 30, yL); gm.lineTo(x1 + 30, yL); gm.stroke();
  gm.strokeStyle = ACC.safe; gm.lineWidth = 2; gm.beginPath(); gm.moveTo(x0, yL); gm.lineTo(x1, yL); gm.stroke(); gm.restore();
  GATES.forEach((gname, i) => { const x = x0 + step * i;
    gm.save(); gm.fillStyle = 'rgba(4,12,22,.9)'; gm.beginPath(); gm.arc(x, yL, 13, 0, 7); gm.fill(); gm.strokeStyle = ACC.safe; gm.lineWidth = 1.6; gm.stroke();
    gm.lineWidth = 2; gm.beginPath(); gm.moveTo(x - 5.5, yL); gm.lineTo(x - 1.5, yL + 4); gm.lineTo(x + 6, yL - 4.5); gm.stroke(); gm.restore();
    txt(gm, String(i + 1).padStart(2, '0'), x, yL - 30, 20, 600, 'rgba(142,224,188,.9)', 'center', 1);
    txt(gm, gname, x, yL + 52, 28, 500, INK, 'center'); });
  txt(gm, '착공 전', x0 - 30, yL - 74, 22, 500, SOFT, 'left', 1);
  caption(gm, '착공 전 관문을 모두 통과 — 안전하게 짓는다', '');
};
addEventListener('resize', render);
FONT_READY.then(render);
</script>
</body>
</html>
