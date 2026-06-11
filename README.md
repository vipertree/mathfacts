# Math Facts

A web app for memorizing math facts — currently addition and subtraction with
sums/minuends up to 20, built to extend to multiplication/division and larger
numbers later.

The student makes **zero study decisions**: an SRS-style algorithm introduces
easy facts first, builds toward harder ones, refreshes older ones, and fades
visual scaffolding as fluency grows. The end goal for every fact: a correct
answer in under 5 seconds with no visual model.

## How it teaches

- **Strategy-tagged facts** (`drill/strategies.py`): every fact carries a
  mental strategy (make-ten, near-doubles, back-to-ten, take-from-ten, teen
  place value, …) and a teaching-order stage. Subtraction is interleaved
  right after the addition ideas it builds on (fact families).
- **Visual models** (`static/drill/js/models/`): ten frames, number lines,
  rekenreks, and part-part-whole bar diagrams, each drawn to *evoke the
  strategy* (9 + 4 shows one dot completing the ten frame; 13 − 5 shows a hop
  back to 10 then 2 more). Models fade per fact: shown → only-after-a-pause →
  gone.
- **SRS** (`drill/srs.py`): Leitner boxes 0–7 with intervals from 1 minute to
  32 days; misses drop two boxes and bring the model back; mastered facts
  still get sprinkled in occasionally for retention.
- **Gentle timing**: a quiet 5-second pace bar; nothing buzzes, questions
  never expire — speed only affects whether the answer counts as *fluent*
  (and timing is measured server-side, so it can't be spoofed).
- **Daily goal**: points come only from answered questions (3 fluent / 2
  correct / 0 wrong), so sitting idle earns nothing. The default 150-point
  goal is roughly 15 minutes of honest practice (tunable per student).

## Running locally

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_facts                  # 462 facts, idempotent
python manage.py createsuperuser             # your admin account
python manage.py create_student kid pass123 --theme pirate
python manage.py runserver 0.0.0.0:8006      # port convention: 8006 = mathfacts
python manage.py test drill                  # 36 tests
```

Students log in with username + password only (no email anywhere). Accounts
are created by the admin via `create_student` or the Django admin (`/admin/`).
Staff can view any student's report at `/report/<username>/`.

## Themes

Pirate, High Tech, and Princess ship now; students switch on their home page.
Adding a theme = one entry in `drill/themes.py` (names, emoji, phrase pools)
+ one CSS custom-property file at `static/drill/themes/<key>.css`. Optional
art drops into `static/drill/themes/<key>/background.webp` (the CSS gradient
shows wherever art is absent).

## Layout

- `config/settings/{base,development,production}.py` — split settings;
  `manage.py` defaults to development. Production expects `.env` (see
  `.env.example`) and mounts at `adderoaks.com/mathfacts/`.
- `drill/` — the single app: models, SRS, strategies, themes, views, tests.
- Practice loop is two JSON endpoints (`/api/next/`, `/api/answer/`) driven
  by vanilla JS; answers by tapping any number 0–20 or typing.
