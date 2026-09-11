/* Visual-model renderers, without a browser.
 *
 *   node --test tests/test_models.mjs
 *
 * Each renderer is a pure function of (container, question) that sets
 * container.innerHTML to an SVG string, so a fake container and a global
 * `window` are the whole harness. What we check is that the picture actually
 * depicts the arithmetic: the right number of dots, cells and hops, parts
 * that add up to the product, and no NaN leaking into the markup.
 */
import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const MODELS_DIR = join(dirname(fileURLToPath(import.meta.url)),
                        '..', 'static', 'drill', 'js', 'models');
const FILES = ['tenframe', 'numberline', 'rekenrek', 'bars',
               'groups', 'array', 'skipline'];

// the renderers are plain browser scripts: give them a window and eval them
const window = {};
globalThis.window = window;
for (const name of FILES) {
  // eslint-disable-next-line no-eval
  eval(readFileSync(join(MODELS_DIR, `${name}.js`), 'utf8'));
}
const MFModels = window.MFModels;

function render(model, q) {
  const container = { innerHTML: '' };
  MFModels[model](container, q);
  return container.innerHTML;
}

function count(html, cls) {
  return (html.match(new RegExp(`class="[^"]*\\b${cls}\\b`, 'g')) || []).length;
}

function assertWellFormed(html, label) {
  assert.ok(html.length > 0, `${label}: rendered nothing`);
  assert.doesNotMatch(html, /NaN|undefined|Infinity/,
                      `${label}: bad number in the SVG`);
  const box = html.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  assert.ok(box, `${label}: no viewBox`);
  const [w, h] = [Number(box[1]), Number(box[2])];
  assert.ok(w > 0 && h > 0, `${label}: empty viewBox ${w}x${h}`);
  assert.ok(w <= 2000 && h <= 2000, `${label}: runaway viewBox ${w}x${h}`);
  const opened = (html.match(/<(rect|circle|line|path|text)\b/g) || []).length;
  assert.ok(opened > 0, `${label}: no shapes drawn`);
}

// every multiplication and division fact in the tables
const MUL_MAX = 10;
const MUL_FACTS = [];
for (let a = 0; a <= MUL_MAX; a++)
  for (let b = 0; b <= MUL_MAX; b++)
    MUL_FACTS.push({ op: 'mul', a, b, answer: a * b });
const DIV_FACTS = [];
for (let b = 1; b <= MUL_MAX; b++)
  for (let q = 0; q <= MUL_MAX; q++)
    DIV_FACTS.push({ op: 'div', a: b * q, b, answer: q });

test('all seven renderers are registered', () => {
  for (const name of ['ten_frame', 'number_line', 'rekenrek', 'bars',
                      'groups', 'array', 'skip_line'])
    assert.strictEqual(typeof MFModels[name], 'function', name);
});

test('every multiplicative model renders every fact well-formed', () => {
  for (const model of ['groups', 'array', 'skip_line']) {
    for (const f of [...MUL_FACTS, ...DIV_FACTS]) {
      const q = { ...f, strategy: 'x' };
      const html = render(model, q);
      // 0 groups / a 0-wide array legitimately draw nothing
      if (html === '') continue;
      assertWellFormed(html, `${model} ${f.op} ${f.a} ${f.b}`);
    }
  }
});

test('equal groups draws one group per group with the right dots in each', () => {
  for (const f of MUL_FACTS) {
    const html = render('groups', { ...f, strategy: 'mul_groups' });
    assert.strictEqual(count(html, 'gp-ring'), f.a, `${f.a}x${f.b} groups`);
    assert.strictEqual(count(html, 'gp-dot'), f.a * f.b, `${f.a}x${f.b} dots`);
  }
});

test('equal groups shares a dividend into divisor-many groups', () => {
  for (const f of DIV_FACTS) {
    const html = render('groups', { ...f, strategy: 'div_share' });
    assert.strictEqual(count(html, 'gp-ring'), f.b, `${f.a}/${f.b} groups`);
    assert.strictEqual(count(html, 'gp-dot'), f.a, `${f.a}/${f.b} dots`);
  }
});

test('equal groups hides the answer for division and shows it for multiplication', () => {
  const div = render('groups', { op: 'div', a: 12, b: 3, strategy: 'div_share' });
  assert.match(div, /class="gp-per">\?</);          // "? in each group"
  const mul = render('groups', { op: 'mul', a: 4, b: 3, strategy: 'mul_groups' });
  assert.match(mul, /class="gp-per">3</);
});

test('array draws rows x columns of cells', () => {
  for (const f of MUL_FACTS) {
    if (f.a < 1 || f.b < 1) continue;
    const html = render('array', { ...f, strategy: 'mul_square' });
    assert.strictEqual(count(html, 'ar-cell'), f.a * f.b, `${f.a}x${f.b}`);
  }
});

test('array shows the divisor as one side and asks for the other', () => {
  for (const f of DIV_FACTS) {
    if (f.a < 1) continue;
    const html = render('array', { ...f, strategy: 'div_think_mul' });
    assert.strictEqual(count(html, 'ar-cell'), f.a, `${f.a}/${f.b} cells`);
    assert.match(html, /ar-unknown/, `${f.a}/${f.b} marks the unknown side`);
    assert.ok(html.includes(`>${f.a}<`), `${f.a}/${f.b} labels the whole`);
  }
});

test('nines are drawn as ten with one strip taken away', () => {
  for (const [a, b] of [[9, 6], [9, 7], [9, 8], [6, 9], [7, 9], [8, 9]]) {
    const html = render('array', { op: 'mul', a, b, answer: a * b,
                                   strategy: 'mul_nine' });
    const ten = a === 9 ? 10 * b : a * 10;
    assert.strictEqual(count(html, 'ar-cell'), ten, `${a}x${b} draws ten of them`);
    assert.strictEqual(count(html, 'ar-strike'), 1, `${a}x${b} strikes the extra`);
    assert.strictEqual(count(html, 'ar-cell-extra'), a === 9 ? b : a,
                       `${a}x${b} fades exactly one strip`);
  }
});

test('break-apart splits the longer side at five and the parts add up', () => {
  for (const [a, b] of [[6, 7], [6, 8], [7, 6], [7, 8], [8, 6], [8, 7]]) {
    const html = render('array', { op: 'mul', a, b, answer: a * b,
                                   strategy: 'mul_break_apart' });
    const parts = [...html.matchAll(/class="ar-part[^"]*">([^<]+)</g)]
      .map(m => m[1]);
    assert.strictEqual(parts.length, 2, `${a}x${b} has two parts`);
    const sum = parts.reduce((t, text) => t + Number(text.split('=')[1]), 0);
    assert.strictEqual(sum, a * b, `${a}x${b} parts sum to the product`);
    // the split is at five along the longer side
    assert.ok(parts.some(p => p.includes('×5') || p.startsWith('5×')),
              `${a}x${b} splits at five: ${parts.join(' + ')}`);
    assert.strictEqual(count(html, 'ar-cell'), a * b);
    assert.ok(count(html, 'ar-cell-b') > 0, `${a}x${b} colours the second part`);
  }
});

test('skip line hops by the family number and lands on the product', () => {
  const cases = [[7, 5, 5, 7], [5, 7, 5, 7], [10, 7, 10, 7], [7, 10, 10, 7],
                 [5, 5, 5, 5], [10, 10, 10, 10], [5, 10, 10, 5], [10, 5, 10, 5]];
  for (const [a, b, step, hops] of cases) {
    const html = render('skip_line', { op: 'mul', a, b, answer: a * b });
    assert.strictEqual(count(html, 'sl-hop') - count(html, 'sl-hop-label'), hops,
                       `${a}x${b} hop count`);
    const landings = [...html.matchAll(/class="sl-num">(\d+)</g)].map(m => Number(m[1]));
    assert.strictEqual(landings.at(-1), a * b, `${a}x${b} ends on the product`);
    assert.ok(html.includes(`+${step}`), `${a}x${b} hops by ${step}`);
  }
});

test('skip line asks how many hops for division', () => {
  for (const [a, b] of [[35, 5], [70, 10], [100, 10], [50, 5]]) {
    const html = render('skip_line', { op: 'div', a, b, answer: a / b });
    assert.strictEqual(count(html, 'sl-hop') - count(html, 'sl-hop-label'), a / b,
                       `${a}/${b} hop count`);
    assert.match(html, /sl-ask/, `${a}/${b} asks for the count`);
    const landings = [...html.matchAll(/class="sl-num">(\d+)</g)].map(m => Number(m[1]));
    assert.strictEqual(landings.at(-1), a, `${a}/${b} ends on the dividend`);
  }
});

test('additive models still render the whole add/sub domain', () => {
  const facts = [];
  for (let a = 0; a <= 20; a++)
    for (let b = 0; b <= 20; b++) {
      if (a + b <= 20) facts.push({ op: 'add', a, b, answer: a + b });
      if (b <= a) facts.push({ op: 'sub', a, b, answer: a - b });
    }
  for (const model of ['ten_frame', 'number_line', 'rekenrek', 'bars']) {
    for (const f of facts) {
      const html = render(model, { ...f, strategy: 'x' });
      if (html === '') continue;
      assertWellFormed(html, `${model} ${f.op} ${f.a} ${f.b}`);
    }
  }
});
