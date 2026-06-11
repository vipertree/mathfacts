/* Rekenrek renderer: two rods of 10 beads (5 red + 5 white each, like the
 * real thing). Beads pushed to the left are "in play".
 *
 * doubles:      a beads on each rod — see the match
 * near_doubles: smaller number on top, bigger below, extra bead highlighted
 * halves:       12 − 6 → 6 + 6 shown, bottom rod's beads crossed out
 * default add:  a on top rod, b on bottom rod
 */
(function () {
  window.MFModels = window.MFModels || {};

  const W = 560, H = 150, X0 = 30, GAP = 50, R = 12, ROWY = [48, 108];

  function rod(y) {
    return `<line x1="${X0 - 14}" y1="${y}" x2="${W - X0 + 14}" y2="${y}" class="rk-rod"/>`;
  }

  // n beads pushed left on rod `row`; extras: set of indices to highlight,
  // crossed: cross out the whole row's pushed beads
  function beads(row, n, opts) {
    opts = opts || {};
    const y = ROWY[row];
    let s = '';
    for (let i = 0; i < 10; i++) {
      const inPlay = i < n;
      // in-play beads pack left; resting beads pack right
      const x = inPlay ? X0 + i * (R * 2 + 2)
                       : W - X0 - (9 - i) * (R * 2 + 2) - GAP + 50;
      const red = i < 5;
      let cls = 'rk-bead ' + (red ? 'rk-red' : 'rk-white') + (inPlay ? '' : ' rk-rest');
      if (opts.extra === i) cls += ' rk-extra';
      s += `<circle cx="${x}" cy="${y}" r="${R}" class="${cls}"/>`;
      if (inPlay && opts.crossed)
        s += `<line x1="${x - R}" y1="${y - R}" x2="${x + R}" y2="${y + R}" class="rk-cross"/>` +
             `<line x1="${x - R}" y1="${y + R}" x2="${x + R}" y2="${y - R}" class="rk-cross"/>`;
    }
    return s;
  }

  window.MFModels.rekenrek = function (container, q) {
    let top, bottom, topOpts = {}, botOpts = {};
    if (q.strategy === 'halves') {        // a − b with a = 2b
      top = q.b; bottom = q.b; botOpts.crossed = true;
    } else if (q.strategy === 'near_doubles') {
      top = Math.min(q.a, q.b); bottom = Math.max(q.a, q.b);
      botOpts.extra = bottom - 1;          // the bead that makes it a near-double
    } else if (q.op === 'sub') {
      // generic subtraction: show a split over two rods, cross out b from the end
      top = Math.min(q.a, 10); bottom = q.a - top;
      // (only used as a fallback; primary sub strategies use other models)
      botOpts.crossed = false;
    } else {
      top = Math.min(q.a, 10); bottom = q.b;  // doubles & generic add
      if (q.strategy === 'doubles' && q.a > 10) { top = 10; bottom = q.a + q.b - 10; }
    }
    const s = rod(ROWY[0]) + rod(ROWY[1]) + beads(0, top, topOpts) + beads(1, bottom, botOpts);
    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" class="model-svg rk-svg" role="img" aria-label="rekenrek">${s}</svg>`;
  };
})();
