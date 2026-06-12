/* Segmented part-whole bar(s).
 *
 * Every quantity is drawn as a row of unit cells, and a bar holds at most ten
 * cells: anything bigger wraps onto another bar. So a teen quantity always
 * shows as a full ten plus the leftover (4 + 11 -> the whole is 15 cells = a
 * bar of ten and a bar of five), which is exactly the place-value / make-ten
 * idea these facts are about.
 *
 * add: the whole (a+b) as one run of `a` cells (colour A) then `b` cells
 *      (colour B), wrapping at ten; the total is the unknown answer.
 * sub: the whole `a` cells, with the last `b` crossed out (taken away); the
 *      cells left over (colour A) are the unknown answer.
 */
(function () {
  window.MFModels = window.MFModels || {};

  const PER_ROW = 10, CW = 28, CH = 30, GAP = 3, ROW_GAP = 12;
  const PADX = 10, PAD_TOP = 28, PAD_BOTTOM = 12;

  const colX = i => PADX + (i % PER_ROW) * (CW + GAP);
  const rowY = i => PAD_TOP + Math.floor(i / PER_ROW) * (CH + ROW_GAP);

  function cell(i, cls, removed) {
    const x = colX(i), y = rowY(i);
    let s = `<rect x="${x}" y="${y}" width="${CW}" height="${CH}" rx="4" class="bar-cell ${cls}"/>`;
    if (removed) {
      const m = 6;
      s += `<line x1="${x + m}" y1="${y + m}" x2="${x + CW - m}" y2="${y + CH - m}" class="bar-cell-x"/>` +
           `<line x1="${x + m}" y1="${y + CH - m}" x2="${x + CW - m}" y2="${y + m}" class="bar-cell-x"/>`;
    }
    return s;
  }

  function label(i, text, cls) {
    const x = colX(i) + CW / 2, y = rowY(i) - 8;
    return `<text x="${x}" y="${y}" class="${cls}">${text}</text>`;
  }

  window.MFModels.bars = function (container, q) {
    const total = q.op === 'add' ? q.a + q.b : q.a;
    if (total < 1) { container.innerHTML = ''; return; }

    let cells = '', labels = '';
    if (q.op === 'add') {
      for (let i = 0; i < total; i++)
        cells += cell(i, i < q.a ? 'bar-cell-a' : 'bar-cell-b');
      if (q.a > 0) labels += label(0, q.a, 'bar-num');
      if (q.b > 0) labels += label(q.a, q.b, 'bar-num');
      // the whole is the unknown — mark the end of the last cell with "= ?"
      const last = total - 1;
      labels += `<text x="${colX(last) + CW + 12}" y="${rowY(last) + CH / 2 + 7}" class="bar-q">= ?</text>`;
    } else {
      const remain = q.a - q.b;
      for (let i = 0; i < total; i++) {
        const removed = i >= remain;
        cells += cell(i, removed ? 'bar-cell-removed' : 'bar-cell-a', removed);
      }
      if (remain > 0) labels += label(0, '?', 'bar-q-label');
      if (q.b > 0) labels += label(remain, q.b, 'bar-num');
    }

    const cols = Math.min(total, PER_ROW);
    const rows = Math.ceil(total / PER_ROW);
    const W = PADX * 2 + cols * CW + (cols - 1) * GAP + (q.op === 'add' ? 52 : 0);
    const H = PAD_TOP + rows * CH + (rows - 1) * ROW_GAP + PAD_BOTTOM;
    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" class="model-svg bars-svg" role="img" aria-label="bar diagram">${cells}${labels}</svg>`;
  };
})();
