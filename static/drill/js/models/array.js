/* Array / area-model renderer.
 *
 * The picture that makes the hard multiplication facts tractable: a rows x b
 * columns rectangle of unit squares, with each side counted on its edge.
 *
 * mul_square:      the plain array — 7 x 7 is visibly a square
 * mul_nine:        the nine-side is drawn as ten with the extra strip struck
 *                  out, so 9 x 6 reads "ten sixes, take one six away"
 * mul_break_apart: the array is split at five along one side and the two
 *                  parts are labelled (7 x 8 -> 7 x 5 and 7 x 3), which is
 *                  the distributive move done with scissors
 * div:             the divisor is the known side and the answer is the other
 *                  one — 56 / 7 draws 7 rows and asks "? columns", with the
 *                  whole area labelled 56
 */
(function () {
  window.MFModels = window.MFModels || {};

  const CELL = 22, GAP = 2;
  const PAD_LEFT = 34, PAD_TOP = 30, PAD_RIGHT = 62, PAD_BOTTOM = 26;
  const SPLIT_GAP = 12;          // extra space opened at a break-apart seam

  window.MFModels.array = function (container, q) {
    // rows x cols, and which side (if any) is the unknown
    let rows, cols, colsUnknown = false, rowsUnknown = false;
    if (q.op === 'mul') {
      rows = q.a; cols = q.b;
    } else {
      rows = q.b; cols = q.b ? q.a / q.b : 0; colsUnknown = true;
    }
    if (rows < 1 || cols < 1) {
      container.innerHTML = '';
      return;
    }

    // A ninth row/column is drawn as ten with the last strip taken away.
    const nine = q.strategy === 'mul_nine';
    const nineRows = nine && rows === 9;
    const nineCols = nine && cols === 9 && !nineRows;
    const drawRows = nineRows ? 10 : rows;
    const drawCols = nineCols ? 10 : cols;

    // Break apart at five along the LONGER side, which leaves the biggest
    // second part: 8 x 6 splits the eight (5x6 + 3x6 = 30 + 18), not the six
    // (which would leave a pointless 8x1 sliver).
    let splitCol = 0, splitRow = 0;
    if (q.strategy === 'mul_break_apart' && Math.max(rows, cols) > 5) {
      if (cols >= rows) splitCol = 5;
      else splitRow = 5;
    }

    const xOf = c => PAD_LEFT + c * (CELL + GAP) + (splitCol && c >= splitCol ? SPLIT_GAP : 0);
    const yOf = r => PAD_TOP + r * (CELL + GAP) + (splitRow && r >= splitRow ? SPLIT_GAP : 0);

    let cells = '', marks = '';
    for (let r = 0; r < drawRows; r++) {
      for (let c = 0; c < drawCols; c++) {
        const extra = (nineRows && r === 9) || (nineCols && c === 9);
        const cls = extra ? 'ar-cell-extra'
          : (splitCol && c >= splitCol) || (splitRow && r >= splitRow)
            ? 'ar-cell-b' : 'ar-cell-a';
        cells += `<rect x="${xOf(c)}" y="${yOf(r)}" width="${CELL}" height="${CELL}"
                   rx="3" class="ar-cell ${cls}"/>`;
      }
    }
    // strike the taken-away strip of a nines fact
    if (nineRows) {
      const y = yOf(9) + CELL / 2;
      marks += `<line x1="${xOf(0)}" y1="${y}" x2="${xOf(drawCols - 1) + CELL}" y2="${y}" class="ar-strike"/>`;
      marks += `<text x="${xOf(drawCols - 1) + CELL + 10}" y="${y + 5}" class="ar-take ar-take-row">−${cols}</text>`;
    } else if (nineCols) {
      const x = xOf(9) + CELL / 2;
      marks += `<line x1="${x}" y1="${yOf(0)}" x2="${x}" y2="${yOf(drawRows - 1) + CELL}" class="ar-strike"/>`;
      marks += `<text x="${x}" y="${yOf(drawRows - 1) + CELL + 18}" class="ar-take">−${rows}</text>`;
    }

    const right = xOf(drawCols - 1) + CELL;
    const bottom = yOf(drawRows - 1) + CELL;

    // side counts: rows down the left, columns across the top
    let labels = '';
    const rowsText = rowsUnknown ? '?' : (nineRows ? '10' : String(rows));
    const colsText = colsUnknown ? '?' : (nineCols ? '10' : String(cols));
    labels += `<text x="${PAD_LEFT - 12}" y="${(PAD_TOP + bottom) / 2 + 6}"
                class="ar-side ${rowsUnknown ? 'ar-unknown' : ''}">${rowsText}</text>`;
    labels += `<text x="${(PAD_LEFT + right) / 2}" y="${PAD_TOP - 10}"
                class="ar-side ${colsUnknown ? 'ar-unknown' : ''}">${colsText}</text>`;

    // the area itself: known (division) or the thing being asked (mul)
    if (q.op === 'div') {
      labels += `<text x="${right + 10}" y="${(PAD_TOP + bottom) / 2 + 6}" class="ar-total">${q.a}</text>`;
    } else if (splitCol || splitRow) {
      // label each part of a broken-apart array with its own product
      const p1 = splitCol ? rows * splitCol : splitRow * cols;
      const p2 = splitCol ? rows * (cols - splitCol) : (rows - splitRow) * cols;
      const t1 = splitCol ? `${rows}×${splitCol} = ${p1}` : `${splitRow}×${cols} = ${p1}`;
      const t2 = splitCol ? `${rows}×${cols - splitCol} = ${p2}` : `${rows - splitRow}×${cols} = ${p2}`;
      if (splitCol) {
        labels += `<text x="${(xOf(0) + xOf(splitCol - 1) + CELL) / 2}" y="${bottom + 18}" class="ar-part">${t1}</text>`;
        labels += `<text x="${(xOf(splitCol) + right) / 2}" y="${bottom + 18}" class="ar-part">${t2}</text>`;
      } else {
        labels += `<text x="${right + 10}" y="${(yOf(0) + yOf(splitRow - 1) + CELL) / 2 + 5}" class="ar-part ar-part-left">${t1}</text>`;
        labels += `<text x="${right + 10}" y="${(yOf(splitRow) + bottom) / 2 + 5}" class="ar-part ar-part-left">${t2}</text>`;
      }
    } else {
      labels += `<text x="${right + 10}" y="${(PAD_TOP + bottom) / 2 + 6}" class="ar-total">= ?</text>`;
    }

    const W = right + PAD_RIGHT;
    const H = bottom + PAD_BOTTOM;
    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" class="model-svg ar-svg" role="img"
        aria-label="array model">${cells}${marks}${labels}</svg>`;
  };
})();
