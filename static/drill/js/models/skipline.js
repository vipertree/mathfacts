/* Skip-counting number line — the ×5 and ×10 families (and ÷5, ÷10).
 *
 * Equal hops along a line, each landing labelled, so the student literally
 * skip-counts: 5, 10, 15, 20, ...
 *
 * mul: hops of five (or ten) — the family's number is always the hop size,
 *      whichever way round the fact is written, and the other factor is how
 *      many hops. 7 x 5 and 5 x 7 both draw seven hops of five.
 * div: the divisor is the hop size and the number of hops is the answer, so
 *      35 / 5 asks "how many hops of five reach 35?" — the hops are drawn
 *      and the last one lands on the dividend.
 */
(function () {
  window.MFModels = window.MFModels || {};

  const W = 560, X0 = 30, X1 = W - 30, Y = 96;
  const H_BASE = 130;      // line + ticks + landing labels
  const H_ASK = 152;       // + a row for division's "? hops"
  const NUM_BASELINE = Y + 26;   // where the landing labels sit

  window.MFModels.skip_line = function (container, q) {
    // hop size and hop count
    let step, hops;
    if (q.op === 'mul') {
      // the 10s or 5s family: that factor is the hop
      step = [10, 5].find(n => q.a === n || q.b === n) || Math.min(q.a, q.b);
      hops = (q.a === step) ? q.b : q.a;
      if (q.a === step && q.b === step) hops = step;   // 5x5 / 10x10
    } else {
      step = q.b;
      hops = q.b ? q.a / q.b : 0;
    }
    const total = step * hops;
    if (!step || hops < 1 || total < 1) { container.innerHTML = ''; return; }

    const H = q.op === 'div' ? H_ASK : H_BASE;
    const px = n => X0 + (X1 - X0) * (n / total);
    let s = `<line x1="${X0}" y1="${Y}" x2="${X1}" y2="${Y}" class="sl-line"/>`;

    // ticks and landing labels at every hop
    for (let i = 0; i <= hops; i++) {
      const n = i * step, x = px(n);
      s += `<line x1="${x}" y1="${Y - 7}" x2="${x}" y2="${Y + 7}" class="sl-tick"/>`;
      s += `<text x="${x}" y="${NUM_BASELINE}" class="sl-num">${n}</text>`;
    }

    // the hops themselves
    const lift = Math.max(16, Math.min(42, 300 / hops));
    for (let i = 0; i < hops; i++) {
      const x1 = px(i * step), x2 = px((i + 1) * step), mid = (x1 + x2) / 2;
      s += `<path d="M ${x1} ${Y - 8} Q ${mid} ${Y - 8 - lift * 2} ${x2} ${Y - 8}"
             class="sl-hop"/>`;
      // label each hop when there is room, otherwise just the first
      if (hops <= 7 || i === 0)
        s += `<text x="${mid}" y="${Y - 12 - lift}" class="sl-hop-label">+${step}</text>`;
    }

    const caption = q.op === 'mul'
      ? `${hops} hop${hops === 1 ? '' : 's'} of ${step}`
      : `how many hops of ${step} reach ${q.a}?`;
    s += `<text x="${W / 2}" y="20" class="sl-caption">${caption}</text>`;
    // below the landing labels, not through them
    if (q.op === 'div')
      s += `<text x="${W / 2}" y="${H - 8}" class="sl-ask">? hops</text>`;

    container.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" class="model-svg sl-svg" role="img"
        aria-label="skip counting number line">${s}</svg>`;
  };
})();
