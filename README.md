# Math Facts

A web app for memorizing math facts — **all four operations**: addition and
subtraction to 20, and the multiplication and division tables to 10 × 10.
A teacher chooses which operations each student practices.

The student makes **zero study decisions**: an SRS-style algorithm introduces
easy facts first, builds toward harder ones, refreshes older ones, and fades
visual scaffolding as fluency grows. The end goal for every fact: a correct
answer in under 5 seconds with no visual model.

## How it teaches

- **Strategy-tagged facts** (`drill/strategies.py`): every fact carries a
  mental strategy (make-ten, near-doubles, back-to-ten, take-from-ten, teen
  place value, skip counting, break-the-array-apart, …) and a teaching-order
  stage. Subtraction is interleaved right after the addition ideas it builds
  on (fact families); division mirrors multiplication the same way.
- **Progression is the batch, variety is inside it.** A batch is homogeneous by
  construction ("addition that bridges ten", "the threes and fours"), so its
  facts are deliberately unordered: shuffled under a fixed seed, then spread so
  consecutive facts answer differently. Ordering a batch by size means ordering
  addition *by its answer*, which is how a student ends up drilling eight ways
  to make 11 and then seven ways to make 12. The SRS widens that further per
  student and steers new facts away from answers already in the working set.
- **Visual models** (`static/drill/js/models/`): ten frames, number lines,
  rekenreks and part-part-whole bars for `+`/`−`; **equal groups**, the
  **array/area model** and a **skip-counting line** for `×`/`÷`. Each is drawn
  to *evoke the strategy*, not just the quantity:
  - 9 + 4 shows one dot completing the ten frame; 13 − 5 hops back to 10 then 2
  - 4 × 3 is four rings of three dots — count the groups
  - 7 × 5 is seven hops of five along a line — skip-count the landings
  - 9 × 6 draws **ten** sixes with the tenth struck out (`−6`)
  - 7 × 8 splits the array at five and labels both parts (7×5 = 35, 7×3 = 21)
  - 56 ÷ 7 draws 7 rows totalling 56 and asks for the number of columns
  - 12 ÷ 3 deals 12 dots into 3 rings and asks how many are in one

  Models fade per fact: shown → only-after-a-pause → gone.
- **SRS** (`drill/srs.py`): Leitner boxes 0–7 with intervals from 1 minute to
  32 days; misses drop two boxes and bring the model back; mastered facts
  still get sprinkled in occasionally for retention.
- **Placement — it works out what the student already knows.** A student
  handed this app is not necessarily a beginner, and walking them batch by
  batch to find that out wastes hundreds of questions.
  - A fact answered right *and* under 5s on its very first exposure is taken as
    already known (`FactProgress.known_on_sight`): it skips most of the ladder
    and finishes after one confirming review instead of six.
  - `Student.reach` is a placement ladder — the batch new facts are drawn from.
    It rises when a new fact turns out to be known and settles **onto** the
    batch where one is missed. In practice a fluent student is answering
    teen-subtraction facts inside a dozen questions.
  - Coverage is not traded away for that: a quarter of introductions come from
    the shallowest batch that still has unseen facts, so every fact is
    eventually tested individually however high `reach` climbs.
  - A share of questions deliberately revisits facts the student is struggling
    with, due or not — otherwise the hard spots quietly vanish from a session.
  - Two failure modes are guarded against explicitly, because both showed up in
    simulation: a handful of impossible facts eating every question (a fact is
    **rested** for a day once it has been missed five times, instead of
    retried on a loop), and a correctly-placed student answering almost
    everything wrong (after a run of misses the scheduler hands back a fact
    they can do). Teachers see the result as "Working on" on the manage page.
  - `drill/tests/test_adaptivity.py` simulates beginners, part-fluent and
    stuck students against the real scheduler and asserts the placement lands
    in the right batch and the wrong-answer share stays in a sane band.
- **Timing**: a pace bar drains over each fact's fluency window (20 s with
  the full picture, 11 s fading, 6 s without). If it empties the question is
  over and scored as a miss. Timing is measured server-side, so it can't be
  spoofed: an answer that arrives after the window (plus a 2 s network grace)
  is a miss even if the client never sent the timeout.
- **Daily goal**: points come only from answered questions (3 fluent / 2
  correct / 0 wrong), so sitting idle earns nothing. The default 150-point
  goal is roughly 15 minutes of honest practice (tunable per student).

## Running locally

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_facts                  # 693 facts, idempotent
python manage.py createsuperuser             # your admin account
python manage.py create_student kid pass123 --theme pirate
python manage.py create_student ada pw --operations mul div   # times tables only
python manage.py runserver 0.0.0.0:8006      # port convention: 8006 = mathfacts
python manage.py test drill                  # 125 tests
node --test tests/test_models.mjs            # 12 renderer tests, no browser
```

Students log in with username + password only (no email anywhere). Accounts
are created by the admin via `create_student` or the Django admin (`/admin/`).
Staff can view any student's report at `/report/<username>/`.

## Choosing what a student practices

Each student is assigned any one or more of the four operations
(`Student.operations`, default addition + subtraction). Set it with the four
checkboxes per row on **Manage students** (`/manage/`), on the add-student
form, with `create_student --operations`, or in the Django admin.

The assignment is a filter over the whole fact domain, so:

- the SRS only ever serves facts from the assigned operations, and a
  multiplication-only student starts at the first `×` batch rather than at
  `0 + 0`;
- the progress report shows one grid per assigned operation, and the totals,
  batch list and "mastered" counts cover only those facts;
- turning an operation **off keeps every bit of progress** — the FactProgress
  rows stay put, so switching it back on resumes exactly where the student
  left off;
- a student can never be left with zero operations (the page refuses, and
  `enabled_operations` falls back to the default pair).

The multiplication and division grids are laid out as times tables. Division
can't use a dividend axis — it would run to 100 — so its grid is
**divisor × answer** with the dividend in the cell: row 7, column 8 is
56 ÷ 7 = 8.

## Themes

Eight ship now — **Pirate**, **High Tech**, **Princess**, **Dinosaur**,
**Deep Sea**, **Space Cadet**, **Bakery** and **Jungle Explorer** (two of them
dark: High Tech and Deep Sea, plus Space Cadet). Students switch on their home
page.
Adding a theme = one entry in `drill/themes.py` (names, emoji, phrase pools,
instructions text) + one CSS custom-property file at
`static/drill/themes/<key>.css` + a `.chip-<key>` rule in `app.css` (the
picker's palette preview) + a `SPECS` entry in `sound.js`. `drill/tests/
test_themes.py` fails if any of those four is missing, and also checks the
palette itself:

- **`--text` must sit firmly on one side of `--panel`** (≥ 7:1). The ×/÷ models
  paint the marks a student has to *count* — group dots, hop arcs — as
  `color-mix(... var(--accent-2) 60%, var(--text))`, so `--text` is the
  contrast anchor. A mid-tone `--text` weakens every one of those at once.
- Those marks must clear **3:1** against both `--panel` and `--panel-soft`
  (they sit inside a group ring, whose fill is `--panel-soft`).
- `--accent` and `--accent-2` must not tint to near-identical fills, or the
  two halves of a broken-apart array stop reading as two halves.

`--panel-soft` is a *background* shade (ten-frame fill, the inside of a group
ring, faded array cells) — keep it a near neighbour of `--panel`, not a
contrasting colour. Optional art drops into
`static/drill/themes/<key>/background.webp` (the CSS gradient shows wherever
art is absent). Each theme also gets its own **answer sounds** and a
theme-flavored **how-to-play** intro (coins / energy / jewels).

Sounds are **synthesized** in `static/drill/js/sound.js` with the Web Audio
API — no audio files, no licensing, works offline, distinct per theme. To use
recorded SFX instead, add them and call from `sound.js` (the
`play(kind, theme)` contract is stable). Good CC0 sources if you go that way:
freesound.org, mixkit.co, kenney.nl.

## Display & accessibility

- **Zoom**: A−/A+ in the top bar scale the whole page (CSS `zoom`), persisted
  per browser in `localStorage`.
- **Sound on/off**: the 🔊 button mutes/unmutes, persisted in `localStorage`.
- **Fonts**: Fredoka (display) + Nunito (body), with Orbitron for the High
  Tech theme, loaded from Google Fonts with a system fallback stack.
- **Instructions**: a how-to-play modal auto-shows once on first login
  (tracked by `Student.seen_instructions`) and is reopenable anytime from the
  "How to play" button on the home screen.

## Layout

- `config/settings/{base,development,production}.py` — split settings;
  `manage.py` defaults to development. Production expects `.env` (see
  `.env.example`) and mounts at `adderoaks.com/mathfacts/`.
- `drill/` — the single app: models, SRS, strategies, themes, views, tests.
- Practice loop is two JSON endpoints (`/api/next/`, `/api/answer/`) driven
  by vanilla JS. `/api/next/` names the `keypad` and the `answer_max` per
  question (`strategies.KEYPAD` / `ANSWER_MAX`): `+` and `−` get a **direct**
  pad — a button per number 0–20, so every answer is one tap — while `×` and
  `÷` share a **0–9 digit pad** with ⌫ and ⏎. Multiplication's answers run to
  100, where 101 buttons would be a wall of numbers, and division uses the
  same pad so the two multiplicative operations type identically.
- A typed answer **submits itself the moment it is complete**: `/api/next/`
  also sends `answer_digits`, so `5` for 5 × 1 fires immediately while 7 × 8
  waits for its second digit. (That tells the client nothing it couldn't work
  out — it is already holding both operands. The server still owns scoring and
  timing, which is what has to be trusted.) ⏎ is only needed to commit an
  answer *shorter* than the real one.
- `MUL_MAX` in `drill/strategies.py` is the only place the table size lives —
  set it to 12 and reseed for the 12s tables; the grids, axes, keypad range
  and tests all derive from it.
