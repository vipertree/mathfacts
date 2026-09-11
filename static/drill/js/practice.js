/* Practice loop: fetch a question, render it (with its visual model per the
 * scaffold level), accept tap or typed answers, send to the server, show
 * gentle feedback, repeat. All study decisions happen server-side.
 */
(function () {
  const root = document.getElementById('practice');
  const NEXT_URL = root.dataset.nextUrl, ANSWER_URL = root.dataset.answerUrl;
  const THEME = JSON.parse(document.getElementById('theme-data').textContent);

  const el = {
    a: document.getElementById('eq-a'),
    op: document.getElementById('eq-op'),
    b: document.getElementById('eq-b'),
    answer: document.getElementById('eq-answer'),
    model: document.getElementById('model-area'),
    feedback: document.getElementById('feedback'),
    numpad: document.getElementById('numpad'),
    pace: document.getElementById('pace-fill'),
    goalFill: document.getElementById('goal-fill'),
    goalText: document.getElementById('goal-text'),
  };

  let q = null, typed = '', locked = true, hintTimer = null, spentTimer = null;
  let answerMax = 20, answerDigits = 0;

  // ---- keypad. Two shapes; the server names which one per question
  // (strategies.KEYPAD), because it is a property of the operation:
  //  * 'direct' (+ and −): a button per number 0-20, so every answer is one
  //    tap and tapping submits straight away.
  //  * 'digits' (× and ÷): a 0-9 pad with ⌫ and ⏎. Multiplication answers run
  //    to 100 — 101 buttons would be a wall of numbers — and division uses the
  //    same pad so the two feel identical to type.
  // `buttons[n]` only exists on the direct pad.
  const DIGITS = ['1','2','3','4','5','6','7','8','9'];
  let buttons = [], padKind = null, padMax = null;

  function padButton(text, cls, onTap) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'num-btn' + (cls ? ' ' + cls : '');
    b.textContent = text;
    b.addEventListener('click', () => { if (!locked) onTap(); });
    el.numpad.appendChild(b);
    return b;
  }

  function buildPad(kind, max) {
    if (kind === padKind && max === padMax) return;   // already the right pad
    padKind = kind; padMax = max;
    el.numpad.innerHTML = '';
    el.numpad.classList.toggle('digits', kind === 'digits');
    buttons = [];
    if (kind === 'direct') {
      for (let n = 0; n <= max; n++) {
        buttons[n] = padButton(n, '', () => submit(n));
      }
    } else {
      DIGITS.forEach(d => padButton(d, '', () => pushDigit(d)));
      padButton('⌫', 'act', backspace);
      padButton('0', '', () => pushDigit('0'));
      padButton('⏎', 'act', () => { if (typed !== '') submit(parseInt(typed, 10)); });
    }
  }

  // Add a digit to the typed answer and submit as soon as it is complete.
  // Complete means either:
  //  * it is as long as the answer (answerDigits) — so "5" for 5 x 1 fires
  //    straight away instead of hanging on for a second digit that would only
  //    make 50-59, or
  //  * no longer string could be a valid answer at all ("13" with a max of
  //    20, anything over 10 with a max of 100).
  // Either way a partial answer is never guessed at, and ⏎ always works.
  function pushDigit(d) {
    const candidate = typed + d;
    if (parseInt(candidate, 10) > answerMax) return;
    if (candidate.length > 1 && candidate[0] === '0') return;   // no "07"
    typed = candidate;
    el.answer.textContent = typed;
    highlight(parseInt(typed, 10));
    const complete = answerDigits > 0 && typed.length >= answerDigits;
    const extendable = ['0'].concat(DIGITS).some(next => {
      const s = typed + next, v = parseInt(s, 10);
      return v <= answerMax && String(v) === s;
    });
    if (complete || !extendable) submit(parseInt(typed, 10));
  }

  function backspace() {
    typed = typed.slice(0, -1);
    el.answer.textContent = typed || '?';
    highlight(typed === '' ? null : parseInt(typed, 10));
  }

  // ---- keyboard: digits + Enter/Backspace, same rules as the pad
  document.addEventListener('keydown', (e) => {
    if (locked) return;
    if (e.key >= '0' && e.key <= '9') {
      pushDigit(e.key);
    } else if (e.key === 'Enter' && typed !== '') {
      submit(parseInt(typed, 10));
    } else if (e.key === 'Backspace') {
      backspace();
    }
  });

  function highlight(n) {
    buttons.forEach((b, i) => { if (b) b.classList.toggle('typed', i === n); });
  }

  function getCookie(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }

  // ---- question lifecycle
  async function loadNext() {
    const res = await fetch(NEXT_URL, { credentials: 'same-origin' });
    showQuestion(await res.json());
  }

  function showQuestion(data) {
    if (data.empty) { showEmpty(data.message); return; }
    q = data; typed = ''; locked = false;
    clearTimeout(hintTimer);
    answerMax = data.answer_max || 20;
    answerDigits = data.answer_digits || 0;
    buildPad(data.keypad === 'digits' ? 'digits' : 'direct', answerMax);
    el.a.textContent = q.a;
    el.op.textContent = q.symbol;
    el.b.textContent = q.b;
    el.answer.textContent = '?';
    clearFeedback();
    highlight(null);
    updateGoal(q.daily);

    el.model.hidden = true;
    el.model.innerHTML = '';
    if (q.scaffold === 2) {
      renderModel();
    } else if (q.scaffold === 1) {
      // fading scaffold: the picture only appears if they need a moment
      hintTimer = setTimeout(renderModel, 6000);
    }

    // gentle pace bar: drains over the real fluency window for this fact
    // (long while learning, tightening toward 5s as the model fades).
    // Nothing happens when it empties — it never fails or rushes the student.
    const paceMs = q.pace_ms || 15000;
    el.pace.classList.remove('spent');
    el.pace.style.transition = 'none';
    el.pace.style.width = '100%';
    void el.pace.offsetWidth; // reflow so the transition restarts
    el.pace.style.transition = 'width ' + paceMs + 'ms linear';
    el.pace.style.width = '0%';
    clearTimeout(spentTimer);
    spentTimer = setTimeout(() => el.pace.classList.add('spent'), paceMs);
  }

  function renderModel() {
    const renderer = window.MFModels && window.MFModels[q.model];
    if (!renderer) return;
    renderer(el.model, q);
    el.model.hidden = false;
  }

  async function submit(n) {
    locked = true;
    clearTimeout(hintTimer);
    clearTimeout(spentTimer);
    el.answer.textContent = n;
    const res = await fetch(ANSWER_URL, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({ fact_id: q.fact_id, answer: n }),
    });
    if (!res.ok) { loadNext(); return; }
    const result = await res.json();
    updateGoal(result.daily);

    if (result.correct) {
      el.answer.classList.add('right');
      playSound(result.goal_just_met ? 'goal' : 'correct');
      // custom practice doesn't award points, so don't show a "+N" tally
      const tally = THEME.custom ? '' : ' +' + result.points_earned + ' ' + THEME.point_icon;
      const msg = result.mastered_now ? '⭐ Fact mastered! ⭐' : pick(THEME.cheers) + tally;
      feedback(msg, 'good');
      setTimeout(() => {
        el.answer.classList.remove('right');
        result.goal_just_met ? celebrate() : loadNext();
      }, 900);
    } else {
      el.answer.textContent = result.answer;
      el.answer.classList.add('shown');
      playSound('wrong');
      renderModel(); // a miss always earns the picture
      feedback(pick(THEME.oops) + '  ' + q.a + ' ' + q.symbol + ' ' + q.b + ' = ' + result.answer, 'soft');
      setTimeout(() => {
        el.answer.classList.remove('shown');
        result.goal_just_met ? celebrate() : loadNext();
      }, 3200);
    }
  }

  // Nothing to practice (a student with no operations assigned, or an unseeded
  // fact table). Say so and stop, rather than spinning on loadNext().
  function showEmpty(message) {
    locked = true;
    q = null;
    clearTimeout(hintTimer);
    clearTimeout(spentTimer);
    el.numpad.innerHTML = '';
    el.model.hidden = true;
    el.a.textContent = ''; el.op.textContent = ''; el.b.textContent = '';
    el.answer.textContent = '';
    feedback(message || 'Nothing to practice yet — ask your teacher.', 'soft');
  }

  function playSound(kind) {
    if (window.MFSound) window.MFSound.play(kind, THEME.key);
  }

  // The feedback element always reserves its space (see .feedback in app.css),
  // so showing a message never shifts the keypad. We only swap text + class.
  function feedback(msg, cls) {
    el.feedback.textContent = msg;
    el.feedback.className = 'feedback ' + cls;
  }
  function clearFeedback() {
    el.feedback.textContent = '';
    el.feedback.className = 'feedback';
  }

  function celebrate() {
    const o = document.createElement('div');
    o.className = 'celebrate-overlay';
    o.innerHTML = '<div class="celebrate-card">' + THEME.goal_met +
                  '<br><small>You can keep going or come back tomorrow!</small></div>';
    o.addEventListener('click', () => { o.remove(); loadNext(); });
    document.body.appendChild(o);
    setTimeout(() => { if (o.parentNode) { o.remove(); loadNext(); } }, 4000);
  }

  function updateGoal(daily) {
    if (!daily || !el.goalFill) return;  // no goal bar in custom-practice mode
    const pct = Math.min(100, Math.round(100 * daily.points / daily.goal));
    el.goalFill.style.width = pct + '%';
    el.goalText.textContent = THEME.point_icon + ' ' + daily.points + ' / ' + daily.goal;
    el.goalFill.classList.toggle('met', daily.met);
  }

  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

  loadNext();
})();
