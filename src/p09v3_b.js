
const CREW = [[104.5, 168, 'cheer', 1], [106.6, 166.5, 'helmet', -1], [108.8, 169, 'jump', 1], [111, 167.2, 'five', 1], [112.1, 167.4, 'five', -1], [114.2, 168.6, 'fist', -1]];
EXTRA_WORLD = () => {
  g.save(); g.globalCompositeOperation = 'lighter';
  const path = [[186, 60, 8.1], [197.6, 54, 8.1], [197.6, -30, 8.1], [194, -38, 8.1], [184, -38, 8.1]];
  for (let i = 0; i < path.length - 1; i++) { const [a, b] = [path[i], path[i + 1]], L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    for (let d = 0; d < L; d += 6) { const t = d / L, x = a[0] + (b[0] - a[0]) * t, y = a[1] + (b[1] - a[1]) * t; if (toCam(x, y, 8.1)[2] < 10) continue;
      const p = P(x, y, 8.1), R = Math.min(10, 1.1 * S(x, y, 8.1)); const c = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], R); c.addColorStop(0, 'rgba(200,255,250,.55)'); c.addColorStop(1, 'rgba(120,230,220,0)'); g.fillStyle = c; g.beginPath(); g.arc(p[0], p[1], R, 0, 7); g.fill(); } }
  g.restore();
  CREW.slice().sort((a, b) => a[1] - b[1]).forEach(([x, y, pose, flip], i) => crewman(x, y, pose, i, flip));
};
POST = gm => {
  // depth of field: everything rendered so far is background -> soften it
  const tmp = document.createElement('canvas'); tmp.width = gm.canvas.width; tmp.height = gm.canvas.height; tmp.getContext('2d').drawImage(gm.canvas, 0, 0);
  gm.save(); gm.setTransform(1, 0, 0, 1, 0, 0); gm.filter = `blur(${5 * DPR}px)`; gm.drawImage(tmp, 0, 0); gm.filter = 'none'; gm.restore();
  // warm haze toward the sun
  gm.save(); gm.globalCompositeOperation = 'screen'; let q = gm.createRadialGradient(430, 190, 10, 430, 190, 1100); q.addColorStop(0, 'rgba(255,214,150,.55)'); q.addColorStop(.35, 'rgba(255,200,130,.15)'); q.addColorStop(1, 'rgba(255,200,130,0)'); gm.fillStyle = q; gm.fillRect(0, 0, W, H); gm.restore();
  // hero worker, sharp
  const keep = g; g = gm; heroWorker(1360, 470, 430); g = keep;
  // light wrap from the bright background onto the hero's front edge, then vignette + grain
  q = gm.createRadialGradient(W * .45, H * .5, H * .45, W * .45, H * .5, H * 1.05); q.addColorStop(0, 'rgba(0,0,0,0)'); q.addColorStop(1, 'rgba(6,12,22,.55)'); gm.fillStyle = q; gm.fillRect(0, 0, W, H);
  gm.save(); gm.globalCompositeOperation = 'overlay'; gm.globalAlpha = .08; gm.fillStyle = gm.createPattern(grain, 'repeat'); gm.fillRect(0, 0, W, H); gm.restore();
  gm.save(); gm.shadowColor = 'rgba(0,10,25,.6)'; gm.shadowBlur = 14; gm.fillStyle = '#FFFFFF'; gm.font = font(500, 60); gm.textAlign = 'left'; gm.textBaseline = 'alphabetic';
  gm.fillText('안전하게 짓고,', 150, 760); gm.fillText('청정수소 1등급으로', 150, 842); gm.restore();
};
addEventListener('resize', render);
FONT_READY.then(render);
</script>
</body>
</html>
