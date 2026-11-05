
/* ============================================================
   HUD — editorial style (after POSCO Studio films):
   soft scrim, hairlines, Medium/SemiBold type, colour used sparingly
   ============================================================ */
const INK = '#FFFFFF', SOFT = 'rgba(255,255,255,.62)', HAIR = 'rgba(255,255,255,.42)';
const ACC = { risk:'#FF9A8B', safe:'#8EE0BC', law:'#A9DDF5', warn:'#FFD978', tq:'#7FDCD3', heat:'#FFC08A' };
function txt(gg, s, x, y, size, w = 500, col = INK, align = 'left', ls = 0) {
  gg.save(); gg.shadowColor = 'rgba(0,8,18,.75)'; gg.shadowBlur = 8;
  gg.font = font(w, size); gg.fillStyle = col; gg.textAlign = align; gg.textBaseline = 'alphabetic';
  if ('letterSpacing' in gg) gg.letterSpacing = ls + 'px'; gg.fillText(s, x, y); if ('letterSpacing' in gg) gg.letterSpacing = '0px';
  gg.restore();
}
function hudWrap(gg, text, maxW) {
  const parts = text.split(' · '), out = []; let cur = '';
  for (const p of parts) { const t = cur ? cur + ' · ' + p : p; if (gg.measureText(t).width > maxW && cur) { out.push(cur + ' ·'); cur = p; } else cur = t; }
  if (cur) out.push(cur); return out;
}
function scrim(gg, x0) {                       // darkens the right side like a film lower-third, no box
  const q = gg.createLinearGradient(x0, 0, W, 0); q.addColorStop(0, 'rgba(4,12,22,0)'); q.addColorStop(.32, 'rgba(4,12,22,.58)'); q.addColorStop(1, 'rgba(4,12,22,.74)');
  gg.fillStyle = q; gg.fillRect(x0, 0, W - x0, H);
}
function scrimL(gg, x1) {                     // same scrim mirrored to the left side
  const q = gg.createLinearGradient(0, 0, x1, 0); q.addColorStop(0, 'rgba(4,12,22,.74)'); q.addColorStop(.68, 'rgba(4,12,22,.58)'); q.addColorStop(1, 'rgba(4,12,22,0)');
  gg.fillStyle = q; gg.fillRect(0, 0, x1, H);
}
function hudTag(gg, text, wx, wy, wz, dx, dy) {
  const [x, y] = P(wx, wy, wz); if (dx === 'auto') dx = x < 560 ? 110 : -110; const ex = x + dx, ey = y + dy, right = dx >= 0;
  gg.save(); gg.shadowColor = 'rgba(0,8,18,.6)'; gg.shadowBlur = 6;
  gg.strokeStyle = HAIR; gg.lineWidth = 1; gg.beginPath(); gg.moveTo(x, y); gg.lineTo(ex, ey); gg.lineTo(ex + (right ? 18 : -18), ey); gg.stroke();
  gg.fillStyle = INK; gg.beginPath(); gg.arc(x, y, 3, 0, 7); gg.fill();
  txt(gg, text, ex + (right ? 26 : -26), ey + 8, 25, 500, INK, right ? 'left' : 'right');
  gg.restore(); return [x, y];
}
function hudMarker(gg, sx, sy, n, col = ACC.risk) {
  gg.save(); gg.strokeStyle = col; gg.lineWidth = 1.6; gg.beginPath(); gg.arc(sx, sy, 24, 0, 7); gg.stroke();
  gg.globalAlpha = .45; gg.lineWidth = 1; gg.beginPath(); gg.arc(sx, sy, 38, 0, 7); gg.stroke(); gg.globalAlpha = 1;
  gg.fillStyle = col; gg.beginPath(); gg.arc(sx, sy, 3, 0, 7); gg.fill();
  gg.lineWidth = 1; gg.beginPath(); gg.moveTo(sx + 27, sy - 27); gg.lineTo(sx + 44, sy - 44); gg.stroke();
  txt(gg, String(n).padStart(2, '0'), sx + 50, sy - 44, 24, 600, col);
  gg.restore();
}
// rows: [[label, text, kind]], laws: [..], badge: {text, kind}
function hudPanel(gg, x, y, w, rows, laws, badge) {
  gg.save();
  let yy = y; const lineX = x - 22;
  const sec = (label, kind) => { gg.fillStyle = ACC[kind] || SOFT; gg.beginPath(); gg.arc(x + 4, yy - 8, 3.5, 0, 7); gg.fill(); txt(gg, label, x + 18, yy, 22, 500, SOFT, 'left', 1); yy += 44; };
  rows.forEach(([lab, text, kind]) => { sec(lab, kind); gg.font = font(500, 30); hudWrap(gg, text, w).forEach(l => { txt(gg, l, x, yy, 30, 500); yy += 42; }); yy += 26; });
  sec('한국 적용 법령', 'law'); laws.forEach(l => { txt(gg, l, x, yy, 27, 500, 'rgba(255,255,255,.92)'); yy += 38; });
  if (badge) { yy += 22; const c = ACC[badge.kind] || ACC.warn; gg.strokeStyle = c; gg.lineWidth = 1.5; gg.beginPath(); gg.moveTo(x, yy - 9); gg.lineTo(x + 22, yy - 9); gg.stroke(); txt(gg, badge.text, x + 34, yy, 26, 500, c); yy += 10; }
  gg.strokeStyle = HAIR; gg.lineWidth = 1; gg.beginPath(); gg.moveTo(lineX, y - 30); gg.lineTo(lineX, yy + 4); gg.stroke();
  gg.restore(); return yy - y;
}
function chevronsOn(gg, pts3, col, spacing = 34, back = false) {
  const sp = pts3.map(p => P(...p)); gg.save(); gg.strokeStyle = col; gg.lineWidth = 2; gg.lineCap = 'round'; gg.lineJoin = 'round';
  for (let i = 0; i < sp.length - 1; i++) { let [a, b] = [sp[i], sp[i + 1]]; if (back) [a, b] = [b, a];
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]), an = Math.atan2(b[1] - a[1], b[0] - a[0]);
    for (let d = spacing / 2; d < L; d += spacing) { const x = a[0] + (b[0] - a[0]) * d / L, y = a[1] + (b[1] - a[1]) * d / L;
      gg.save(); gg.translate(x, y); gg.rotate(an); gg.beginPath(); gg.moveTo(-5, -6); gg.lineTo(3, 0); gg.lineTo(-5, 6); gg.stroke(); gg.restore(); } }
  gg.restore();
}
function iconPowerOff(gg, x, y, col = ACC.risk) {
  gg.save(); gg.strokeStyle = col; gg.lineWidth = 1.8; gg.beginPath(); gg.arc(x, y, 22, 0, 7); gg.stroke();
  gg.beginPath(); gg.moveTo(x + 3, y - 13); gg.lineTo(x - 6, y + 2); gg.lineTo(x + 2, y + 2); gg.lineTo(x - 3, y + 13); gg.stroke();
  gg.beginPath(); gg.moveTo(x - 15, y - 15); gg.lineTo(x + 15, y + 15); gg.stroke(); gg.restore();
}
function iconShield(gg, x, y, col = ACC.safe) {
  gg.save(); gg.strokeStyle = col; gg.lineWidth = 1.8; gg.beginPath(); gg.moveTo(x, y - 18); gg.lineTo(x + 15, y - 11); gg.lineTo(x + 13, y + 7); gg.lineTo(x, y + 18); gg.lineTo(x - 13, y + 7); gg.lineTo(x - 15, y - 11); gg.closePath(); gg.stroke();
  gg.beginPath(); gg.moveTo(x - 6, y); gg.lineTo(x - 1, y + 5); gg.lineTo(x + 7, y - 5); gg.stroke(); gg.restore();
}
function readout(gg, s, x, y, col = ACC.heat) {          // value with a thin leader, no pill
  gg.save(); gg.strokeStyle = col; gg.lineWidth = 1; gg.beginPath(); gg.moveTo(x, y); gg.lineTo(x + 46, y - 30); gg.lineTo(x + 70, y - 30); gg.stroke();
  gg.fillStyle = col; gg.beginPath(); gg.arc(x, y, 3, 0, 7); gg.fill();
  gg.shadowColor = 'rgba(0,8,18,.6)'; gg.shadowBlur = 6; txt(gg, s, x + 78, y - 20, 32, 500, col); gg.restore();
}
