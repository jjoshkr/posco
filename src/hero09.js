
/* ---------- hero: close profile of a worker looking at the plant (reference: POSCO film profile shots) ----------
   local units: 1 = head height (chin to crown), origin at the ear canal, facing left (toward the plant) */
function heroWorker(ox, oy, s) {
  const X = x => ox + x * s, Y = y => oy + y * s;
  const M = (x, y) => g.moveTo(X(x), Y(y)), L = (x, y) => g.lineTo(X(x), Y(y));
  const Qc = (cx, cy, x, y) => g.quadraticCurveTo(X(cx), Y(cy), X(x), Y(y));
  const Cc = (a, b, c, d, e, f) => g.bezierCurveTo(X(a), Y(b), X(c), Y(d), X(e), Y(f));
  const blob = (x, y, rx, ry, rgb, a, rot = 0) => { g.save(); g.translate(X(x), Y(y)); g.rotate(rot); g.scale(rx / ry, 1);
    const q = g.createRadialGradient(0, 0, 0, 0, 0, ry * s); q.addColorStop(0, `rgba(${rgb},${a})`); q.addColorStop(1, `rgba(${rgb},0)`); g.fillStyle = q; g.beginPath(); g.arc(0, 0, ry * s, 0, 7); g.fill(); g.restore(); };
  const stroke = (col, w, fn, blur = 0) => { g.save(); if (blur) { g.shadowColor = col; g.shadowBlur = blur; } g.strokeStyle = col; g.lineWidth = w * s; g.lineCap = 'round'; g.lineJoin = 'round'; g.beginPath(); fn(); g.stroke(); g.restore(); };
  const lgH = (x0, x1, stops) => { const q = g.createLinearGradient(X(x0), 0, X(x1), 0); stops.forEach(([o, c]) => q.addColorStop(o, c)); return q; };
  const r = rng(808);

  /* ---- jacket: torso, near arm, collar ---- */
  const torso = () => { g.beginPath(); M(-.3, .6); Cc(-.42, .68, -.5, .86, -.52, 1.7); L(.74, 1.7); Cc(.76, 1.3, .74, .95, .66, .74); Qc(.56, .6, .44, .54); Qc(.38, .5, .3, .46); Qc(0, .5, -.3, .6); g.closePath(); };
  torso(); g.fillStyle = lgH(-.52, .76, [[0, '#2F62A6'], [.12, '#24508C'], [.6, '#204780'], [1, '#183A6C']]); g.fill();
  g.save(); torso(); g.clip();
  // chest reflective band + placket
  g.fillStyle = lgH(-.64, .2, [[0, '#F4F1E6'], [.5, '#BFC3BE'], [1, '#7E848A']]); g.beginPath(); M(-.7, 1.18); Qc(-.3, 1.12, .2, 1.16); L(.2, 1.26); Qc(-.3, 1.22, -.7, 1.28); g.closePath(); g.fill();
  stroke('rgba(8,16,30,.55)', .006, () => { M(-.34, .66); Cc(-.42, .78, -.46, 1.0, -.48, 1.7); });
  for (let i = 0; i < 2600; i++) { const x = -.75 + r() * 1.75, y = .5 + r() * 1.25; stroke(r() > .5 ? 'rgba(255,255,255,.018)' : 'rgba(0,0,0,.035)', .0025, () => { M(x, y); L(x + .008, y - .008); }); }
  // chest pocket with flap, button and pen
  g.fillStyle = 'rgba(0,0,0,.12)'; g.beginPath(); M(-.42, .9); L(-.18, .88); L(-.17, 1.1); L(-.42, 1.12); g.closePath(); g.fill();
  stroke('rgba(255,255,255,.22)', .003, () => { M(-.41, .91); L(-.19, .89); L(-.18, 1.09); L(-.41, 1.11); g.closePath(); });
  g.fillStyle = 'rgba(255,255,255,.06)'; g.beginPath(); M(-.43, .87); L(-.17, .85); L(-.17, .93); Qc(-.3, .97, -.43, .95); g.closePath(); g.fill();
  stroke('rgba(0,0,0,.35)', .004, () => { M(-.43, .95); Qc(-.3, .97, -.17, .93); });
  g.fillStyle = '#16304F'; g.beginPath(); g.arc(X(-.3), Y(.94), .013 * s, 0, 7); g.fill();
  g.fillStyle = '#C9CFD6'; g.fillRect(X(-.24), Y(.8), .014 * s, .12 * s); g.fillStyle = '#1A1D22'; g.fillRect(X(-.242), Y(.78), .018 * s, .035 * s);
  // buttons on the placket
  [[-.37, .78], [-.465, 1.38], [-.475, 1.6]].forEach(([x, y]) => { g.fillStyle = '#14294A'; g.beginPath(); g.arc(X(x), Y(y), .014 * s, 0, 7); g.fill(); g.fillStyle = 'rgba(255,255,255,.35)'; g.beginPath(); g.arc(X(x) - .004 * s, Y(y) - .004 * s, .004 * s, 0, 7); g.fill(); });
  stroke('rgba(255,255,255,.16)', .003, () => { M(-.31, .66); Cc(-.39, .78, -.43, 1.0, -.45, 1.7); });
  // stitched edges of the chest band
  g.save(); g.setLineDash([.012 * s, .01 * s]); stroke('rgba(60,60,60,.45)', .0025, () => { M(-.7, 1.19); Qc(-.3, 1.13, .2, 1.17); M(-.7, 1.27); Qc(-.3, 1.21, .2, 1.25); }); g.restore();
  // muscle volume under the jacket: trapezius ridge, lats, pecs
  // fabric folds
  [[-.4, .92, -.3, 1.02, -.34, 1.1], [.6, .85, .66, 1.1, .64, 1.4]].forEach(([a, b, c, d, e, f]) => stroke('rgba(5,12,25,.1)', .03, () => { M(a, b); Qc(c, d, e, f); }, 10));
  g.restore();
  stroke('rgba(255,206,150,.85)', .01, () => { M(-.3, .6); Cc(-.42, .68, -.5, .86, -.52, 1.7); }, 14);       // warm rim on the chest edge
  // near arm (sleeve) with reflective band
  const arm = () => { g.beginPath(); M(-.08, .8); Cc(-.15, .98, -.16, 1.3, -.14, 1.7); L(.42, 1.7); Cc(.44, 1.3, .46, 1.0, .43, .8); Cc(.36, .64, .03, .63, -.08, .8); g.closePath(); };
  arm(); g.fillStyle = lgH(-.16, .46, [[0, '#2B5B9C'], [.4, '#24508C'], [1, '#1B3F72']]); g.fill();
  g.save(); arm(); g.clip();
  g.fillStyle = lgH(-.2, .6, [[0, '#F1EEE4'], [.45, '#C3C6C1'], [1, '#6E747B']]); g.beginPath(); M(-.25, 1.14); Qc(.18, 1.22, .62, 1.12); L(.62, 1.22); Qc(.18, 1.32, -.25, 1.24); g.closePath(); g.fill();
  for (let i = 0; i < 900; i++) { const x = -.2 + r() * .8, y = .62 + r() * 1.1; stroke(r() > .5 ? 'rgba(255,255,255,.018)' : 'rgba(0,0,0,.035)', .0025, () => { M(x, y); L(x + .008, y - .008); }); }
  g.save(); g.setLineDash([.012 * s, .01 * s]); stroke('rgba(60,60,60,.45)', .0025, () => { M(-.25, 1.15); Qc(.18, 1.23, .62, 1.13); M(-.25, 1.23); Qc(.18, 1.31, .62, 1.21); });
  stroke('rgba(255,255,255,.2)', .0028, () => { M(-.05, .84); Qc(.15, .72, .44, .8); M(.4, .9); Cc(.42, 1.1, .55, 1.4, .54, 1.7); }); g.restore();
  // embroidered safety patch (green cross) on the sleeve
  { const c = [X(.2), Y(.98)], R = .075 * s; g.fillStyle = '#E9E4D2'; g.beginPath(); g.arc(c[0], c[1], R, 0, 7); g.fill(); g.strokeStyle = '#2E7A48'; g.lineWidth = .008 * s; g.beginPath(); g.arc(c[0], c[1], R * .86, 0, 7); g.stroke();
    g.fillStyle = '#2E8A4E'; g.fillRect(c[0] - R * .16, c[1] - R * .55, R * .32, R * 1.1); g.fillRect(c[0] - R * .55, c[1] - R * .16, R * 1.1, R * .32);
    g.save(); g.setLineDash([.006 * s, .005 * s]); g.strokeStyle = 'rgba(60,60,40,.5)'; g.lineWidth = .002 * s; g.beginPath(); g.arc(c[0], c[1], R * .98, 0, 7); g.stroke(); g.restore();
    const q = g.createLinearGradient(c[0] - R, 0, c[0] + R, 0); q.addColorStop(0, 'rgba(255,255,255,.15)'); q.addColorStop(1, 'rgba(0,0,30,.35)'); g.fillStyle = q; g.beginPath(); g.arc(c[0], c[1], R, 0, 7); g.fill(); }
  [[.02, .9, .18, 1.02, .14, 1.1], [.36, .95, .3, 1.1, .38, 1.4]].forEach(([a, b, c, d, e, f]) => stroke('rgba(5,12,25,.1)', .03, () => { M(a, b); Qc(c, d, e, f); }, 10));
  stroke('rgba(150,180,220,.25)', .008, () => { M(-.06, .8); Qc(.12, .7, .3, .79); });     // shoulder seam catch-light
  g.restore();
  stroke('rgba(255,206,150,.55)', .007, () => { M(-.08, .8); Cc(-.15, .98, -.16, 1.3, -.14, 1.7); }, 10);

  /* ---- collar back (behind the neck) ---- */
  g.beginPath(); M(.1, .7); Qc(.17, .55, .26, .5); Qc(.36, .47, .44, .52); Qc(.47, .62, .4, .74); g.closePath();
  g.fillStyle = lgH(.14, .45, [[0, '#1B3B69'], [.6, '#22487F'], [1, '#2A5590']]); g.fill();
  stroke('rgba(150,180,225,.35)', .006, () => { M(.17, .56); Qc(.24, .5, .33, .48); Qc(.41, .47, .44, .52); });       // folded top edge

  /* ---- neck: slimmer, shaded, flowing into the collar ---- */
  const neck = () => { g.beginPath(); M(-.25, .4); Qc(-.236, .46, -.218, .5); Qc(-.206, .53, -.212, .57); Qc(-.214, .65, -.205, .74); L(.26, .72); Qc(.25, .36, .31, .12); L(.22, .06); L(-.05, .18); L(-.26, .35); g.closePath(); };
  neck(); g.fillStyle = lgH(-.22, .28, [[0, '#EEC6AA'], [.35, '#DDAE91'], [.75, '#C4937A'], [1, '#A57861']]); g.fill();
  g.save(); neck(); g.clip();
  blob(-.06, .37, .32, .075, '125,82,62', .5, -.38);                                                   // shadow cast by the jaw
  stroke('rgba(255,228,210,.1)', .09, () => { M(.06, .3); Qc(-.03, .46, -.14, .66); }, 30);          // sternocleidomastoid catching light
  stroke('rgba(130,86,66,.1)', .08, () => { M(.15, .32); Qc(.08, .5, -.02, .7); }, 30);              // and the hollow behind it
  blob(-.212, .52, .02, .03, '255,226,206', .35);                                                      // soft Adam's apple
  blob(.0, .64, .28, .06, '95,58,42', .5, -.12);                                                      // collar shadow on the neck
  g.restore();
  stroke('rgba(255,214,180,.55)', .006, () => { M(-.25, .42); Qc(-.236, .46, -.218, .5); Qc(-.206, .53, -.212, .57); Qc(-.214, .65, -.205, .72); }, 8);

  /* ---- collar front: wraps round the neck, then the shirt-style collar point ---- */
  g.beginPath(); M(.24, .55); Qc(.04, .69, -.24, .66); L(-.28, .78); Qc(.03, .82, .38, .66); g.closePath();
  g.fillStyle = lgH(-.28, .34, [[0, '#3466A8'], [.45, '#24508C'], [1, '#163360']]); g.fill();
  stroke('rgba(170,200,240,.4)', .005, () => { M(.24, .55); Qc(.04, .69, -.24, .66); });                // rolled top edge catches light
  stroke('rgba(5,12,25,.35)', .012, () => { M(.22, .57); Qc(.04, .7, -.22, .675); }, 6);              // shadow where the collar meets the neck
  g.beginPath(); M(-.25, .67); Qc(-.1, .75, .08, .73); L(-.04, .89); Qc(-.2, .84, -.42, .87); Qc(-.33, .75, -.25, .67); g.closePath();
  g.fillStyle = lgH(-.42, .08, [[0, '#3F72B6'], [.5, '#2A5694'], [1, '#1A3A6A']]); g.fill();
  g.save(); g.setLineDash([.01 * s, .008 * s]); stroke('rgba(255,255,255,.22)', .0025, () => { M(-.38, .85); Qc(-.2, .81, -.08, .85); }); g.restore();
  stroke('rgba(0,0,0,.3)', .005, () => { M(-.42, .875); Qc(-.2, .84, -.05, .895); });
  stroke('rgba(255,206,150,.6)', .005, () => { M(-.25, .67); Qc(-.33, .75, -.42, .87); }, 6);

  /* ---- head: young man, neutral expression (after the reference photo) ---- */
  const profile = () => {
    M(-.4, -.3); Qc(-.43, -.22, -.432, -.15); Qc(-.44, -.11, -.428, -.085);          // forehead, soft brow, nasion
    Qc(-.468, -.01, -.522, .07); Qc(-.54, .1, -.522, .122);                           // straight high bridge, rounded tip
    Qc(-.505, .138, -.474, .136); Qc(-.452, .142, -.447, .158);                       // under the tip, columella
    Qc(-.448, .18, -.468, .205); Qc(-.466, .222, -.44, .228);                         // philtrum, upper lip
    Qc(-.462, .242, -.455, .262); Qc(-.44, .284, -.42, .292);                         // full lower lip, labiomental fold
    Qc(-.43, .33, -.414, .358); Qc(-.394, .402, -.33, .408);                          // small chin, underside
  };
  const head = () => { g.beginPath(); profile(); Qc(-.18, .39, -.03, .265); Qc(.1, .24, .2, .2); Qc(.37, .14, .395, -.04); Qc(.4, -.22, .34, -.3); g.closePath(); };
  head(); g.fillStyle = lgH(-.56, .4, [[0, '#F8DECB'], [.2, '#EFC9AE'], [.6, '#D9A98E'], [1, '#B3826A']]); g.fill();
  g.save(); head(); g.clip();
  blob(-.16, -.19, .32, .11, '95,60,45', .42);                        // shade from the brim and the fringe
  blob(-.37, -.06, .07, .045, '120,78,60', .28);                      // eye socket, soft
  blob(-.31, .06, .14, .1, '255,236,220', .4);                        // smooth cheek plane in the sun
  blob(-.34, .13, .08, .06, '232,138,118', .16);                      // light blush
  blob(-.2, .2, .13, .1, '175,115,90', .1);                           // gentle cheekbone shading
  blob(-.16, .35, .22, .045, '140,92,70', .22, -.5);                  // under the jaw line
  blob(-.47, .145, .03, .016, '120,70,55', .4);                       // under the nose tip
  blob(-.435, .282, .035, .016, '130,80,62', .32);                     // under the lower lip
  stroke('rgba(255,240,228,.6)', .008, () => { M(-.438, -.07); Qc(-.47, -.005, -.515, .065); });          // bridge highlight
  stroke('rgba(150,90,72,.45)', .005, () => { M(-.492, .128); Qc(-.475, .118, -.462, .128); });          // nostril
  stroke('rgba(170,110,90,.3)', .005, () => { M(-.462, .095); Qc(-.448, .11, -.452, .135); });           // nose wing, faint
  // lips: gentle smile, corners lifted, a little of the upper teeth showing (no folds)
  g.fillStyle = 'rgba(206,122,110,.55)'; g.beginPath(); M(-.468, .205); Qc(-.466, .217, -.446, .221); L(-.384, .208); Qc(-.42, .2, -.468, .205); g.closePath(); g.fill();
  g.fillStyle = '#F3EEE8'; g.beginPath(); M(-.446, .221); L(-.39, .211); Qc(-.405, .226, -.44, .231); g.closePath(); g.fill();
  g.fillStyle = 'rgba(214,132,120,.5)'; g.beginPath(); M(-.44, .232); Qc(-.462, .242, -.455, .262); Qc(-.425, .264, -.392, .222); g.closePath(); g.fill();
  stroke('rgba(110,55,48,.6)', .0045, () => { M(-.39, .212); Qc(-.378, .209, -.368, .197); });            // lifted corner
  blob(-.37, .2, .014, .01, '150,90,70', .35);                                                         // soft dimple shade
  stroke('rgba(255,236,226,.5)', .004, () => { M(-.452, .25); Qc(-.44, .258, -.424, .252); });
  blob(-.35, .1, .09, .06, '255,226,208', .35);                                                        // raised cheek
  blob(-.35, .135, .07, .05, '236,140,120', .14);
  // eye in profile, drawn cleanly: rounded cornea at the front, lids meeting at the outer corner
  blob(-.38, -.07, .065, .035, '150,100,80', .2);                                                      // soft socket shade
  const eyeP = () => { g.beginPath(); M(-.417, -.082); Qc(-.384, -.088, -.352, -.068); Qc(-.382, -.05, -.411, -.049); Qc(-.425, -.065, -.417, -.082); g.closePath(); };
  eyeP(); { const q = g.createLinearGradient(X(-.425), 0, X(-.35), 0); q.addColorStop(0, '#F4ECE7'); q.addColorStop(1, '#D9C7BD'); g.fillStyle = q; g.fill(); }
  g.save(); eyeP(); g.clip();
  { const ix = X(-.409), iy = Y(-.066), q = g.createRadialGradient(ix, iy, 0, ix, iy, .02 * s); q.addColorStop(0, '#6A4630'); q.addColorStop(.75, '#3F2819'); q.addColorStop(1, '#22150D'); g.fillStyle = q; g.beginPath(); g.ellipse(ix, iy, .012 * s, .0175 * s, 0, 0, 7); g.fill(); }
  g.fillStyle = '#0E0806'; g.beginPath(); g.ellipse(X(-.412), Y(-.066), .005 * s, .009 * s, 0, 0, 7); g.fill();
  g.fillStyle = '#FFFFFF'; g.beginPath(); g.arc(X(-.414), Y(-.073), .0032 * s, 0, 7); g.fill();
  blob(-.39, -.08, .04, .01, '110,70,55', .4);                                                         // upper lid shadow on the eyeball
  g.restore();
  // upper lid edge: crisp, slightly thicker at the front, tapering to the outer corner
  g.fillStyle = '#1A100B'; g.beginPath(); M(-.42, -.083); Qc(-.384, -.093, -.35, -.068); Qc(-.384, -.086, -.417, -.079); g.closePath(); g.fill();
  // lower lid: barely there
  stroke('rgba(150,100,82,.3)', .0028, () => { M(-.41, -.049); Qc(-.38, -.05, -.354, -.066); });
  // natural double-lid crease: a soft fold just above the lid, fading toward the front
  stroke('rgba(150,98,78,.28)', .006, () => { M(-.404, -.094); Qc(-.38, -.101, -.352, -.077); }, 3);
  stroke('rgba(255,236,224,.35)', .006, () => { M(-.408, -.088); Qc(-.384, -.094, -.358, -.074); }, 2);   // lid skin highlight
  // lashes: a few short ones flicking forward at the front
  [[-.418, -.083, -.03], [-.411, -.087, -.025], [-.404, -.089, -.02]].forEach(([x, y, d]) => stroke('rgba(20,12,8,.85)', .0026, () => { M(x, y); Qc(x - .006, y - .008, x + d * .45, y - .009); }));
  // hair: long fringe over the forehead, side hair over the ear top, shaggy back hair to the nape
  const HAIR = '#110C0A';
  g.fillStyle = HAIR; g.beginPath(); M(-.52, -.25); L(.02, -.262); L(.01, -.17); Qc(-.25, -.15, -.5, -.19); g.closePath(); g.fill();
  { const rs = rng(31); for (let k = 0; k < 26; k++) { const x0 = -.5 + k * .02 + (rs() - .5) * .01, tip = -.085 - rs() * .055 - (k > 22 ? .04 : 0) - (k < 2 ? .05 : 0), w = .018 + rs() * .014, lean = -.015 - rs() * .02; const tipC = (x0 > -.45 && x0 < -.31) ? Math.min(tip, -.122) : tip;
    g.fillStyle = k % 3 ? HAIR : '#1A1310'; g.beginPath(); M(x0 - w, -.2); Qc(x0 - w * .4 + lean * .4, (tipC - .2) / 2, x0 + lean, tipC); Qc(x0 + w * .5 + lean * .3, (tipC - .2) / 2, x0 + w, -.2); g.closePath(); g.fill(); }
    for (let k = 0; k < 18; k++) { const x0 = -.46 + rs() * .44; stroke(`rgba(105,96,92,${.18 + rs() * .2})`, .003, () => { M(x0, -.245); Qc(x0 - .004, -.21, x0 - .01, -.175); }); } }
  g.restore();
  // side + back hair (outside the head clip so it can stand off the skull)
  g.fillStyle = HAIR; g.beginPath(); M(-.08, -.26); L(.13, -.27); Qc(.12, -.17, .08, -.135); Qc(.02, -.15, -.01, -.12); Qc(-.03, -.04, -.045, .03); Qc(-.07, -.06, -.08, -.26); g.closePath(); g.fill();
  // short back and sides: a close crop that follows the skull and fades out above the nape
  g.save(); head(); g.clip();
  g.beginPath(); M(.09, -.3); L(.45, -.32); L(.45, .22); L(.25, .2); Qc(.17, .13, .14, .05); Qc(.12, -.1, .09, -.3); g.closePath();
  { const q = g.createLinearGradient(0, Y(-.3), 0, Y(.18)); q.addColorStop(0, 'rgba(18,13,11,.96)'); q.addColorStop(.45, 'rgba(22,17,15,.9)'); q.addColorStop(.72, 'rgba(45,42,46,.45)'); q.addColorStop(1, 'rgba(60,58,62,0)'); g.fillStyle = q; g.fill(); }
  for (let i = 0; i < 700; i++) { const x = .12 + r() * .3, y = -.28 + r() * .36; g.fillStyle = `rgba(${r() > .5 ? '10,8,7' : '90,84,82'},${.12 + r() * .18})`; g.fillRect(X(x), Y(y), 1.4, 1.4); }
  blob(.32, -.15, .08, .06, '140,132,128', .16);                                                         // soft sheen
  g.restore();
  for (let i = 0; i < 30; i++) { const x = -.46 + r() * .44, y = -.25 + r() * .04;
    stroke(`rgba(95,88,84,${.15 + r() * .18})`, .004, () => { M(x, y); Qc(x - .01, y + .02, x - .02, y + .045); }); }
  // ear: helix, antihelix with crura, concha, ear canal behind the tragus, antitragus, fleshy lobe
  const ear = () => { g.beginPath(); M(.0, -.115); Cc(.03, -.172, .132, -.172, .147, -.06); Cc(.157, .02, .123, .08, .097, .11);
    Cc(.088, .14, .082, .19, .047, .197); Cc(.017, .203, .0, .173, .004, .142); Qc(.0, .1, -.01, .07); Qc(-.02, -.05, .0, -.115); g.closePath(); };
  ear(); g.fillStyle = lgH(-.02, .16, [[0, '#EDBCA3'], [.55, '#DCA088'], [1, '#BC7E66']]); g.fill();
  g.save(); ear(); g.clip();
  stroke('rgba(140,72,56,.45)', .016, () => { M(.016, -.103); Cc(.044, -.15, .122, -.15, .13, -.06); Cc(.137, .0, .112, .058, .088, .092); }, 6);   // groove inside the helix rim
  // concha bowl + ear canal
  g.beginPath(); M(.016, -.022); Cc(.05, -.046, .088, -.022, .086, .028); Cc(.086, .072, .06, .092, .04, .092); Cc(.022, .092, .014, .064, .014, .044); g.closePath();
  { const q = g.createRadialGradient(X(.035), Y(.035), 0, X(.04), Y(.03), .06 * s); q.addColorStop(0, 'rgba(110,52,40,.75)'); q.addColorStop(1, 'rgba(160,90,72,.25)'); g.fillStyle = q; g.fill(); }
  g.fillStyle = 'rgba(70,30,22,.85)'; g.beginPath(); g.ellipse(X(.022), Y(.036), .009 * s, .013 * s, 0, 0, 7); g.fill();
  blob(.062, -.035, .028, .02, '130,64,50', .5);                                                       // cymba (upper bowl)
  g.restore();
  stroke('rgba(255,214,196,.32)', .02, () => { M(.03, -.096); Cc(.07, -.112, .104, -.072, .103, -.03); Cc(.103, .02, .088, .06, .066, .086); }, 10);   // antihelix ridge
  stroke('rgba(255,214,196,.25)', .014, () => { M(.062, -.074); Qc(.045, -.055, .028, -.046); }, 8);                                                        // inferior crus
  // tragus flap covering the front of the canal
  g.beginPath(); M(-.011, .006); Qc(.022, .0, .025, .032); Qc(.024, .058, -.008, .058); g.closePath(); g.fillStyle = '#DCA389'; g.fill();
  stroke('rgba(255,222,205,.4)', .006, () => { M(.0, .008); Qc(.021, .006, .022, .03); }, 4);
  stroke('rgba(255,214,196,.3)', .012, () => { M(.034, .1); Qc(.05, .092, .062, .096); }, 6);           // antitragus
  blob(.048, .165, .03, .026, '240,170,150', .55);                                                     // soft pink lobe
  stroke('rgba(255,222,205,.6)', .005, () => { M(.003, -.112); Cc(.033, -.168, .13, -.168, .144, -.06); Cc(.153, .02, .12, .078, .095, .108); }, 4);   // rim light on the helix
  g.save(); head(); g.clip(); stroke('rgba(150,100,80,.22)', .02, () => { M(.015, .255); Qc(-.005, .19, .0, .13); }, 10); g.restore();
  stroke('rgba(125,82,64,.35)', .004, () => { M(-.33, .408); Qc(-.18, .39, -.03, .265); }, 2);
  // soft warm rim along the profile
  g.save(); head(); g.clip(); stroke('rgba(255,226,190,.75)', .01, profile, 14); stroke('rgba(255,242,228,.6)', .003, profile); g.restore();
  // grey webbing chin strap in front of the ear, buckle under the jaw
  stroke('#5B5F66', .03, () => { M(.0, -.25); Qc(-.04, .08, -.25, .43); });
  stroke('rgba(255,255,255,.18)', .004, () => { M(.012, -.24); Qc(-.026, .08, -.238, .422); });
  stroke('rgba(0,0,0,.3)', .004, () => { M(-.012, -.25); Qc(-.054, .08, -.262, .438); });
  g.save(); g.translate(X(-.205), Y(.385)); g.rotate(-1.0); g.fillStyle = '#44484F'; g.beginPath(); g.roundRect(-.022 * s, -.016 * s, .044 * s, .032 * s, .006 * s); g.fill(); g.fillStyle = 'rgba(255,255,255,.18)'; g.fillRect(-.018 * s, -.012 * s, .036 * s, .006 * s); g.restore();

  /* ---- helmet ---- */
  g.save(); g.translate(X(-.02), Y(-.245)); g.scale(.95, .95); g.translate(-X(-.06), -Y(-.25));
  const helmet = () => { g.beginPath(); M(-.6, -.255); Cc(-.58, -.55, -.36, -.82, -.02, -.82); Cc(.28, -.82, .46, -.6, .43, -.3); L(.41, -.235); Qc(0, -.27, -.38, -.232); Qc(-.5, -.236, -.6, -.255); g.closePath(); };
  helmet(); { const q = g.createLinearGradient(X(-.6), Y(-.8), X(.45), Y(-.25)); q.addColorStop(0, '#FFFFFF'); q.addColorStop(.45, '#F0F0EC'); q.addColorStop(.8, '#C6CBD1'); q.addColorStop(1, '#98A0AB'); g.fillStyle = q; g.fill(); }
  g.save(); helmet(); g.clip();
  blob(-.3, -.64, .18, .05, '255,255,255', .9, -.5);
  stroke('rgba(150,158,168,.6)', .012, () => { M(-.48, -.44); Cc(-.4, -.72, -.15, -.78, .05, -.77); Cc(.25, -.76, .38, -.62, .4, -.42); });
  stroke('rgba(255,255,255,.9)', .006, () => { M(-.49, -.46); Cc(-.41, -.74, -.15, -.8, .05, -.79); });
  g.fillStyle = 'rgba(80,88,100,.25)'; g.beginPath(); M(-.6, -.255); Qc(-.5, -.236, -.38, -.232); Qc(0, -.27, .41, -.235); L(.42, -.28); Qc(0, -.31, -.38, -.27); Qc(-.5, -.272, -.59, -.29); g.closePath(); g.fill();
  g.save(); g.translate(X(.09), Y(-.5)); g.transform(1, .06, -.08, 1, 0, 0); g.font = font(600, .135 * s); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#0D3F7A'; g.fillText('POSCO', 0, 0); g.restore();
  g.fillStyle = '#F2C230'; g.beginPath(); M(-.08, -.405); Qc(.1, -.39, .27, -.4); L(.27, -.36); Qc(.1, -.35, -.08, -.365); g.closePath(); g.fill();
  g.fillStyle = 'rgba(120,90,10,.35)'; g.fillRect(X(-.08), Y(-.367), .35 * s, .005 * s);
  { const c = [X(-.33), Y(-.47)], R = .045 * s; g.fillStyle = '#F7F7F2'; g.beginPath(); g.arc(c[0], c[1], R, 0, 7); g.fill(); g.strokeStyle = '#2E8A4E'; g.lineWidth = .006 * s; g.stroke();
    g.fillStyle = '#2E8A4E'; g.fillRect(c[0] - R * .18, c[1] - R * .62, R * .36, R * 1.24); g.fillRect(c[0] - R * .62, c[1] - R * .18, R * 1.24, R * .36); }
  
  g.restore();
  stroke('rgba(255,236,205,.9)', .006, () => { M(-.6, -.255); Cc(-.58, -.55, -.36, -.82, -.02, -.82); }, 12);
  g.fillStyle = '#2A2E36'; g.beginPath(); g.roundRect(X(.3), Y(-.255), .1 * s, .06 * s, .01 * s); g.fill();       // ratchet at the back
  g.restore();
}
