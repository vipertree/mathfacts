/* Number-line renderer (0–20).
 *
 * count_on_1/2:  start at a, unit hops forward
 * count_back_1/2: start at a, unit hops back
 * count_up:      dots at both numbers, a "?" gap arc between (think distance)
 * back_to_ten:   13 − 5 → one arc back to 10, then a second arc for the rest
 * default:       a single labeled jump
 */
(function () {
  window.MFModels = window.MFModels || {};

  const W = 560, H = 120, X0 = 24, X1 = W - 24, Y = 78;
  const px = n => X0 + (X1 - X0) * (n / 20);

  function arc(from, to, label, cls) {
    const x1 = px(from), x2 = px(to), mid = (x1 + x2) / 2;
    const lift = Math.min(46, 14 + Math.abs(x2 - x1) * 0.35);
    return `<path d="M ${x1} ${Y - 6} Q ${mid} ${Y - 6 - lift} ${x2} ${Y - 6}" class="nl-arc ${cls || ''}"/>` +
           `<text x="${mid}" y="${Y - 12 - lift / 2}" class="nl-arc-label">${label}</text>`;
  }

  function base() {
    let s = `<line x1="${X0}" y1="${Y}" x2="${X1}" y2="${Y}" class="nl-line"/>`;
    for (let n = 0; n <= 20; n++) {
      const big = n % 5 === 0;
      s += `<line x1="${px(n)}" y1="${Y - (big ? 8 : 5)}" x2="${px(n)}" y2="${Y + (big ? 8 : 5)}" class="nl-tick"/>`;
      if (big) s += `<text x="${px(n)}" y="${Y + 26}" class="nl-num">${n}</text>`;
    }
    return s;
  }

  function dot(n, cls) {
    return `<circle cx="${px(n)}" cy="${Y}" r="7" class="nl-dot ${cls || ''}"/>` +
           `<text x="${px(n)}" y="${Y - 14}" class="nl-num nl-dot-label">${n}</text>`;
  }

  window.MFModels.number_line = function (container, q) {
    let s = base();
    const st = q.strategy;
    if (st === 'count_on_1' || st === 'count_on_2') {
      const start = Math.max(q.a, q.b), hops = Math.min(q.a, q.b);
      s += dot(start, 'nl-start');
      for (let i = 0; i < hops; i++) s += arc(start + i, start + i + 1, '+1');
    } else if (st === 'count_back_1' || st === 'count_back_2') {
      s += dot(q.a, 'nl-start');
      for (let i = 0; i < q.b; i++) s += arc(q.a - i, q.a - i - 1, '−1');
    } else if (st === 'count_up') {
      s += dot(q.b, 'nl-start') + dot(q.a, 'nl-end') + arc(q.b, q.a, '?', 'nl-gap');
    } else if (st === 'back_to_ten') {
      const first = q.a - 10, rest = q.b - first;
      s += dot(q.a, 'nl-start') + arc(q.a, 10, `−${first}`) + arc(10, 10 - rest, `−${rest}`);
    } else if (q.op === 'add') {
      s += dot(q.a, 'nl-start') + arc(q.a, q.a + q.b, `+${q.b}`);
    } else {
      s += dot(q.a, 'nl-start') + arc(q.a, q.a - q.b, `−${q.b}`);
    }
    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" class="model-svg nl-svg" role="img" aria-label="number line">${s}</svg>`;
  };
})();
