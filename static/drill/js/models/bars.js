/* Part-part-whole bar diagram.
 *
 * add: two known parts, whole = ?
 * sub: known whole (a), known part (b), other part = ?
 * Any value over 10 gets a dashed 10-divider so teen structure (13 = 10 + 3)
 * is visible — that's the strategy for plus_ten / teen facts.
 */
(function () {
  window.MFModels = window.MFModels || {};

  const W = 560, BARH = 46, GAP = 14, PADX = 16, PADY = 10;

  function seg(x, y, w, label, cls, splitAtTen, value) {
    let s = `<rect x="${x}" y="${y}" width="${w}" height="${BARH}" rx="8" class="bar ${cls}"/>` +
            `<text x="${x + w / 2}" y="${y + BARH / 2 + 7}" class="bar-label">${label}</text>`;
    if (splitAtTen && value > 10) {
      const tx = x + w * (10 / value);
      s += `<line x1="${tx}" y1="${y + 4}" x2="${tx}" y2="${y + BARH - 4}" class="bar-split"/>` +
           `<text x="${x + w * (10 / value) / 2}" y="${y - 4}" class="bar-tiny">10</text>` +
           `<text x="${tx + (x + w - tx) / 2}" y="${y - 4}" class="bar-tiny">${value - 10}</text>`;
    }
    return s;
  }

  window.MFModels.bars = function (container, q) {
    const whole = q.op === 'add' ? q.a + q.b : q.a;
    const innerW = W - PADX * 2;
    const px = v => Math.max(innerW * (v / whole), 44); // floor so tiny parts stay tappable/readable
    const H = PADY * 2 + BARH * 2 + GAP + 14;
    const yTop = PADY + 14, yBot = yTop + BARH + GAP;
    let s = '';

    if (q.op === 'add') {
      s += seg(PADX, yTop, innerW, '?', 'bar-unknown', false, 0);
      let wA = px(q.a), wB = px(q.b);
      const scale = innerW / (wA + wB); wA *= scale; wB *= scale;
      s += seg(PADX, yBot, wA - 3, q.a, 'bar-part-a', true, q.a);
      s += seg(PADX + wA + 3, yBot, wB - 3, q.b, 'bar-part-b', true, q.b);
    } else {
      s += seg(PADX, yTop, innerW, q.a, 'bar-whole', true, q.a);
      let wB = px(q.b), wRest = px(q.a - q.b);
      const scale = innerW / (wB + wRest); wB *= scale; wRest *= scale;
      s += seg(PADX, yBot, wRest - 3, '?', 'bar-unknown', false, 0);
      s += seg(PADX + wRest + 3, yBot, wB - 3, q.b, 'bar-part-b', false, q.b);
    }
    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" class="model-svg bars-svg" role="img" aria-label="bar diagram">${s}</svg>`;
  };
})();
