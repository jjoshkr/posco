
/* ============================================================
   CERTIFICATION CHART v3 — readable at a glance
   grade bands behind the bars (values from the handoff: 1등급 ≤0.1 · 2등급 ≤1.0 · 3등급 ≤2.0 · 4등급 ≤4.0),
   large receipt on the left, big value labels, frontal pseudo-3D bars
   ============================================================ */
const GB = [
  { lo:2.0, hi:4.0, name:'4등급', rule:'≤4.0', fill:'rgba(194,103,42,.13)', ink:'#B0581F' },
  { lo:1.0, hi:2.0, name:'3등급', rule:'≤2.0', fill:'rgba(196,150,40,.11)', ink:'#9A7516' },
  { lo:0.1, hi:1.0, name:'2등급', rule:'≤1.0', fill:'rgba(80,150,90,.11)', ink:'#3E7D4A' },
  { lo:-99, hi:0.1, name:'1등급', rule:'≤0.1', fill:'rgba(27,163,156,.16)', ink:'#137F79' }
];
function chartFrame(vmin, vmax) {
  const X0 = 860, X1 = 1590, top = 150, bot = 900, k = (bot - top) / (vmax - vmin);
  return { X0, X1, top, bot, k, Y: v => bot - (Math.max(vmin, Math.min(vmax, v)) - vmin) * k, vmin, vmax };
}
function drawBands(F) {
  GB.forEach(b => { const y0 = F.Y(b.hi), y1 = F.Y(Math.max(b.lo, F.vmin));
    g.fillStyle = b.fill; g.fillRect(F.X0 - 40, y0, F.X1 - F.X0 + 80, y1 - y0);
    const ym = Math.max(y0 + 30, Math.min(y1 - 12, (y0 + y1) / 2 + 12));
    T(b.name, F.X1 + 66, ym, 34, 600, b.ink); T(b.rule, F.X1 + 66 + 108, ym, 26, 500, b.ink); });
  // above 4.0: not clean hydrogen
  g.fillStyle = 'rgba(120,110,100,.06)'; g.fillRect(F.X0 - 40, F.top - 20, F.X1 - F.X0 + 80, F.Y(4.0) - F.top + 20);
  // 4.0 line
  g.save(); g.setLineDash([12, 8]); g.strokeStyle = SK.red; g.lineWidth = 2; g.beginPath(); g.moveTo(F.X0 - 40, F.Y(4)); g.lineTo(F.X1 + 40, F.Y(4)); g.stroke(); g.restore();
  T('청정수소 기준 4.0', F.X1 + 40, F.Y(4) - 14, 26, 600, SK.red, 'right');
  // zero axis
  g.strokeStyle = 'rgba(42,38,34,.75)'; g.lineWidth = 2; g.beginPath(); g.moveTo(F.X0 - 40, F.Y(0)); g.lineTo(F.X1 + 40, F.Y(0)); g.stroke();
  T('0', F.X0 - 56, F.Y(0) + 9, 24, 500, SK.soft, 'right');
  T('kgCO₂e/kgH₂', F.X0 - 40, F.top - 34, 24, 500, SK.soft);
}
function bar3(F, xc, v0, v1, col, w = 120) {
  const yt = F.Y(Math.max(v0, v1)), yb = F.Y(Math.min(v0, v1)), x = xc - w / 2, dx = 22, dy = -14, h = Math.max(6, yb - yt);
  g.save(); g.filter = 'blur(10px)'; g.fillStyle = 'rgba(60,45,30,.22)'; g.fillRect(x + 8, yt + 10, w + dx, h); g.restore();
  // front
  let q = g.createLinearGradient(x, 0, x + w, 0); q.addColorStop(0, shade(col, .12)); q.addColorStop(.5, col); q.addColorStop(1, shade(col, -.12));
  g.fillStyle = q; g.fillRect(x, yt, w, h);
  g.fillStyle = 'rgba(255,255,255,.16)'; g.fillRect(x + 6, yt, w * .22, h);
  // side
  g.fillStyle = shade(col, -.3); g.beginPath(); g.moveTo(x + w, yt); g.lineTo(x + w + dx, yt + dy); g.lineTo(x + w + dx, yt + h + dy); g.lineTo(x + w, yt + h); g.closePath(); g.fill();
  // top
  g.fillStyle = shade(col, .35); g.beginPath(); g.moveTo(x, yt); g.lineTo(x + dx, yt + dy); g.lineTo(x + w + dx, yt + dy); g.lineTo(x + w, yt); g.closePath(); g.fill();
  return { x, yt, yb, w };
}
function receipt(rows, x, y) {
  // rows: [label, value, style] ; style: 'b' bold, 'hr' rule, 'res' result line
  rows.forEach(([l, v, st, col]) => {
    if (st === 'hr') { g.strokeStyle = SK.ink; g.lineWidth = 2; g.beginPath(); g.moveTo(x, y - 30); g.lineTo(x + 560, y - 30); g.stroke(); y += 30; return; }
    if (st === 'res') { T(l, x, y + 10, 48, 600, col || SK.ink); y += 84; return; }
    const size = st === 'b' ? 40 : 36, wgt = st === 'b' ? 600 : 500, c = col || SK.ink;
    T(l, x, y, size, wgt, c); T(v, x + 560, y, size, 600, c, 'right');
    g.save(); g.setLineDash([2, 7]); g.strokeStyle = 'rgba(42,38,34,.3)'; g.lineWidth = 1.5; g.font = font(wgt, size);
    const lw = g.measureText(l).width, vw = g.measureText(v).width; g.beginPath(); g.moveTo(x + lw + 18, y - 10); g.lineTo(x + 560 - vw - 18, y - 10); g.stroke(); g.restore();
    y += st === 'b' ? 74 : 66; });
  return y;
}
function shotChart(stage) {
  cove();
  const L = 130;
  T('수소 1kg의 탄소 영수증', L, 200, 50, 600);
  if (stage === 'A') {
    T('kgCO₂e/kgH₂ · KEEI 산정', L, 246, 24, 500, SK.soft);
    receipt([
      ['원료 가스', '3.177'],
      ['물·탈루', '+0.061'],
      ['전기 (재생·원전)', '0', '', SK.green],
      ['', '', 'hr'],
      ['소계', '3.238', 'b'],
      ['→ 4등급', '', 'res', '#B0581F']
    ], L, 340);
    const F = chartFrame(-.6, 4.7); drawBands(F);
    const a = bar3(F, 980, 0, 3.177, '#7D93AD'), b = bar3(F, 1190, 3.177, 3.238, '#8FA6C2', 110), c = bar3(F, 1410, 0, 3.238, '#2E4C70');
    T('3.177', 980, a.yt - 30, 40, 600, SK.ink, 'center'); T('+0.061', 1190, b.yt - 30, 34, 600, SK.soft, 'center'); T('3.238', 1410, c.yt - 30, 40, 600, SK.ink, 'center');
    g.save(); g.setLineDash([4, 6]); g.strokeStyle = 'rgba(42,38,34,.45)'; g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(a.x + a.w, F.Y(3.177)); g.lineTo(b.x, F.Y(3.177)); g.moveTo(b.x + b.w, F.Y(3.238)); g.lineTo(c.x, F.Y(3.238)); g.stroke(); g.restore();
    [['원료 가스', 980], ['물·탈루', 1190], ['소계', 1410]].forEach(([n, x]) => T(n, x, F.Y(0) + 50, 30, 500, SK.ink, 'center'));
    // call-out: the subtotal ends inside the 4등급 band
    g.strokeStyle = '#B0581F'; g.lineWidth = 2.5; g.beginPath(); g.moveTo(c.x + c.w + 30, F.Y(3.238) + 4); g.lineTo(F.X1 + 50, F.Y(3.0)); g.stroke();
    g.fillStyle = '#B0581F'; g.beginPath(); g.arc(c.x + c.w + 30, F.Y(3.238) + 4, 6, 0, 7); g.fill();
  } else {
    T('고체탄소 크레딧 반영 · KEEI 산정', L, 246, 24, 500, SK.soft);
    receipt([
      ['소계', '3.238'],
      ['고체탄소 크레딧', '−8.0', '', SK.tq],
      ['  3.2kg × 2.5', '', '', SK.soft],
      ['', '', 'hr'],
      ['최종', '−4.762', 'b', SK.tq],
      ['→ 청정수소 1등급', '', 'res', '#137F79']
    ], L, 340);
    const F = chartFrame(-5.7, 4.7); drawBands(F);
    const a = bar3(F, 980, 0, 3.238, '#2E4C70'), b = bar3(F, 1190, 3.238, -4.762, '#1BA39C', 110), c = bar3(F, 1410, 0, -4.762, '#137F79');
    T('3.238', 980, a.yt + 56, 38, 600, '#FFFFFF', 'center');
    T('−8.0', 1190, F.Y(-.4), 44, 600, '#FFFFFF', 'center');
    T('−4.762', 1410, c.yb + 56, 44, 600, '#137F79', 'center');
    g.save(); g.setLineDash([4, 6]); g.strokeStyle = 'rgba(42,38,34,.45)'; g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(a.x + a.w, F.Y(3.238)); g.lineTo(b.x, F.Y(3.238)); g.moveTo(b.x + b.w, F.Y(-4.762)); g.lineTo(c.x, F.Y(-4.762)); g.stroke(); g.restore();
    [['소계', 980, F.Y(0) + 50], ['크레딧', 1190, F.Y(3.238) - 82], ['최종', 1410, F.Y(0) - 22]].forEach(([n, x, y]) => T(n, x, y, 30, 500, SK.ink, 'center'));
    g.strokeStyle = '#137F79'; g.lineWidth = 2.5; g.beginPath(); g.moveTo(c.x + c.w + 30, F.Y(-4.762) + 4); g.lineTo(F.X1 + 50, F.Y(-2.4)); g.stroke();
    g.fillStyle = '#137F79'; g.beginPath(); g.arc(c.x + c.w + 30, F.Y(-4.762) + 4, 6, 0, 7); g.fill();
  }
  vignette(); grainPass();
}
