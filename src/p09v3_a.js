

/* ============================================================
   PLATE 09A v3 — close profile of a worker, plant and cheering crew out of focus
   ============================================================ */
const CAMQ = (new URLSearchParams(location.search).get('cam') || '').split(',').map(Number);
SHOT = () => { const q = CAMQ.length === 7 ? CAMQ : [128, 196, 3.4, 96, 70, 9, 46]; setCam([q[0], q[1], q[2]], [q[3], q[4], q[5]], q[6]); };
NO_TREES.push([40, 150, 220, 330]);
tree = (orig => function (x, y, s, seed) { if (toCam(x, y, 0)[2] < 95) return; orig(x, y, s, seed); })(tree);
window.SUNXY = [430, 190];
