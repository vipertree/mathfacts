/* Ten-frame renderer (double frame, holds 0–20).
 *
 * add: first operand's dots in color A, second in color B, filling the
 *      frames in order — make-ten facts naturally show the second color
 *      completing the first frame (9 + 4 → one dot fills the frame, 3 spill).
 * sub: all `a` dots drawn, with `b` of them crossed out. take_from_ten
 *      crosses out from the FULL first frame (14 − 9 → take 9 from the 10,
 *      the 4 ones survive); everything else crosses out from the end.
 */
(function () {
  window.MFModels = window.MFModels || {};

  const CELL = 34, PAD = 6, R = 11;

  function frameRect(x0, y0) {
    let s = `<rect x="${x0}" y="${y0}" width="${CELL * 5}" height="${CELL * 2}"
             class="tf-frame"/>`;
    for (let i = 1; i < 5; i++)
      s += `<line x1="${x0 + i * CELL}" y1="${y0}" x2="${x0 + i * CELL}" y2="${y0 + CELL * 2}" class="tf-line"/>`;
    s += `<line x1="${x0}" y1="${y0 + CELL}" x2="${x0 + CELL * 5}" y2="${y0 + CELL}" class="tf-line"/>`;
    return s;
  }

  // center of slot i (0..19): slots 0-9 in frame 1, 10-19 in frame 2
  function slotCenter(i) {
    const frame = Math.floor(i / 10), within = i % 10;
    const col = within % 5, row = Math.floor(within / 5);
    const x0 = PAD + frame * (CELL * 5 + 24);
    return [x0 + col * CELL + CELL / 2, PAD + row * CELL + CELL / 2];
  }

  window.MFModels.ten_frame = function (container, q) {
    const total = q.op === 'add' ? q.a + q.b : q.a;
    const frames = total > 10 || q.a > 10 || (q.op === 'add' && q.a + q.b > 10) ? 2 : 1;
    const W = PAD * 2 + frames * CELL * 5 + (frames - 1) * 24;
    const H = PAD * 2 + CELL * 2;
    let s = '';
    for (let f = 0; f < frames; f++) s += frameRect(PAD + f * (CELL * 5 + 24), PAD);

    if (q.op === 'add') {
      for (let i = 0; i < q.a + q.b; i++) {
        const [x, y] = slotCenter(i);
        s += `<circle cx="${x}" cy="${y}" r="${R}" class="${i < q.a ? 'tf-dot-a' : 'tf-dot-b'}"/>`;
      }
    } else {
      const crossed = new Set();
      if (q.strategy === 'take_from_ten') {
        for (let i = 0; i < q.b; i++) crossed.add(i);        // take from the full ten
      } else {
        for (let i = q.a - q.b; i < q.a; i++) crossed.add(i); // take from the end
      }
      for (let i = 0; i < q.a; i++) {
        const [x, y] = slotCenter(i);
        const out = crossed.has(i);
        s += `<circle cx="${x}" cy="${y}" r="${R}" class="${out ? 'tf-dot-out' : 'tf-dot-a'}"/>`;
        if (out) s += `<line x1="${x - R}" y1="${y - R}" x2="${x + R}" y2="${y + R}" class="tf-cross"/>` +
                      `<line x1="${x - R}" y1="${y + R}" x2="${x + R}" y2="${y - R}" class="tf-cross"/>`;
      }
    }
    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" class="model-svg tf-svg" role="img" aria-label="ten frame">${s}</svg>`;
  };
})();
