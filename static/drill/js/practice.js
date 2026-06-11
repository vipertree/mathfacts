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

  // ---- numpad: every answer 0-20 is one tap away
  const buttons = [];
  for (let n = 0; n <= 20; n++) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'num-btn';
    b.textContent = n;
    b.addEventListener('click', () => { if (!locked) submit(n); });
    el.numpad.appendChild(b);
    buttons.push(b);
  }

  // ---- keyboard: digits + Enter/Backspace; auto-submit when the typed
  // string can't be the start of any other valid answer (e.g. "13", "0", "9")
  document.addEventListener('keydown', (e) => {
    if (locked) return;
    if (e.key >= '0' && e.key <= '9') {
      const candidate = typed + e.key;
      if (parseInt(candidate, 10) <= 20) {
        typed = candidate;
        el.answer.textContent = typed;
        highlight(parseInt(typed, 10));
        // can another digit still make a different valid answer? ("1" -> 10..19
        // possible, wait; "13"/"0"/"9" -> nothing longer is valid, submit now)
        const extendable = ['0','1','2','3','4','5','6','7','8','9'].some(d => {
          const s = typed + d, v = parseInt(s, 10);
          return v <= 20 && String(v) === s;
        });
        if (!extendable) submit(parseInt(typed, 10));
      }
    } else if (e.key === 'Enter' && typed !== '') {
      submit(parseInt(typed, 10));
    } else if (e.key === 'Backspace') {
      typed = typed.slice(0, -1);
      el.answer.textContent = typed || '?';
      highlight(typed === '' ? null : parseInt(typed, 10));
    }
  });

  function highlight(n) {
    buttons.forEach((b, i) => b.classList.toggle('typed', i === n));
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
    q = data; typed = ''; locked = false;
    clearTimeout(hintTimer);
    el.a.textContent = q.a;
    el.op.textContent = q.symbol;
    el.b.textContent = q.b;
    el.answer.textContent = '?';
    el.feedback.hidden = true;
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
      feedback(pick(THEME.cheers) + ' +' + result.points_earned + ' ' + THEME.point_icon, 'good');
      if (result.mastered_now) feedback('⭐ Fact mastered! ⭐', 'good');
      setTimeout(() => {
        el.answer.classList.remove('right');
        result.goal_just_met ? celebrate() : loadNext();
      }, 900);
    } else {
      el.answer.textContent = result.answer;
      el.answer.classList.add('shown');
      renderModel(); // a miss always earns the picture
      feedback(pick(THEME.oops) + '  ' + q.a + ' ' + q.symbol + ' ' + q.b + ' = ' + result.answer, 'soft');
      setTimeout(() => {
        el.answer.classList.remove('shown');
        result.goal_just_met ? celebrate() : loadNext();
      }, 3200);
    }
  }

  function feedback(msg, cls) {
    el.feedback.textContent = msg;
    el.feedback.className = 'feedback ' + cls;
    el.feedback.hidden = false;
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
    if (!daily) return;
    const pct = Math.min(100, Math.round(100 * daily.points / daily.goal));
    el.goalFill.style.width = pct + '%';
    el.goalText.textContent = THEME.point_icon + ' ' + daily.points + ' / ' + daily.goal;
    el.goalFill.classList.toggle('met', daily.met);
  }

  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

  loadNext();
})();
