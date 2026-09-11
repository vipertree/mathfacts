/* Equal-groups renderer — "count my groups".
 *
 * The model everything multiplicative starts from: some number of groups,
 * the same amount in each one.
 *
 * mul: `a` groups holding `b` dots each (a x b read as "a groups of b").
 *      4 x 0 draws four visibly empty groups, which is the whole point of
 *      that fact; 0 x b draws none at all.
 * div: the sharing story — `a / b` draws `b` groups with the dividend dealt
 *      out evenly between them, so the student reads the answer off one
 *      group ("? in each group"). 0 / 5 is five empty groups.
 */
(function () {
  window.MFModels = window.MFModels || {};

  const PER_ROW = 5;            // groups per row before wrapping
  const DOT_R = 7, DOT_COL = 20, DOT_ROW = 20, DOTS_PER_ROW = 5;
  const G_PADX = 12, G_PADY = 12, GAP_X = 14, GAP_Y = 16;
  const PADX = 8, PAD_TOP = 26, PAD_BOTTOM = 14;
  const LABEL_DROP = 17;   // clear of a round (empty) group's bottom edge

  // A group box sized for `per` dots (up to 10, laid out 5 to a row).
  function groupSize(per) {
    const cols = Math.max(1, Math.min(per, DOTS_PER_ROW));
    const rows = Math.max(1, Math.ceil(per / DOTS_PER_ROW));
    return [G_PADX * 2 + cols * DOT_COL, G_PADY * 2 + rows * DOT_ROW];
  }

  function group(x, y, w, h, per, cls) {
    let s = `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${Math.min(18, h / 2)}"
             class="gp-ring ${cls || ''}"/>`;
    const cols = Math.min(per, DOTS_PER_ROW);
    const rows = Math.ceil(per / DOTS_PER_ROW);
    const x0 = x + (w - cols * DOT_COL) / 2 + DOT_COL / 2;
    const y0 = y + (h - rows * DOT_ROW) / 2 + DOT_ROW / 2;
    for (let i = 0; i < per; i++) {
      const cx = x0 + (i % DOTS_PER_ROW) * DOT_COL;
      const cy = y0 + Math.floor(i / DOTS_PER_ROW) * DOT_ROW;
      s += `<circle cx="${cx}" cy="${cy}" r="${DOT_R}" class="gp-dot"/>`;
    }
    return s;
  }

  window.MFModels.groups = function (container, q) {
    // how many groups, and how many in each
    let count, per, perLabel;
    if (q.op === 'mul') {
      count = q.a; per = q.b; perLabel = String(q.b);
    } else {
      count = q.b; per = q.b ? q.a / q.b : 0; perLabel = '?';
    }
    if (count < 1) {                      // 0 x 7: there are no groups at all
      container.innerHTML =
        '<svg viewBox="0 0 240 60" class="model-svg gp-svg" role="img" ' +
        'aria-label="no groups"><text x="120" y="38" class="gp-none">' +
        'no groups at all</text></svg>';
      return;
    }

    const [gw, gh] = groupSize(per);
    const cols = Math.min(count, PER_ROW);
    const rows = Math.ceil(count / PER_ROW);
    let s = '';
    for (let i = 0; i < count; i++) {
      const x = PADX + (i % PER_ROW) * (gw + GAP_X);
      const y = PAD_TOP + Math.floor(i / PER_ROW) * (gh + GAP_Y);
      s += group(x, y, gw, gh, per, per ? '' : 'gp-empty');
      // label what is inside each group (a "?" when that is the answer)
      s += `<text x="${x + gw / 2}" y="${y + gh + LABEL_DROP}" class="gp-per">${perLabel}</text>`;
    }
    const W = PADX * 2 + cols * gw + (cols - 1) * GAP_X;
    const H = PAD_TOP + rows * gh + (rows - 1) * GAP_Y + PAD_BOTTOM + 8;
    const caption = q.op === 'mul'
      ? `${count} group${count === 1 ? '' : 's'} of ${per}`
      : `${q.a} shared into ${count} group${count === 1 ? '' : 's'}`;
    s = `<text x="${W / 2}" y="17" class="gp-caption">${caption}</text>` + s;
    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" class="model-svg gp-svg" role="img"
        aria-label="equal groups">${s}</svg>`;
  };
})();
