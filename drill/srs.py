"""
The scheduling brain. Students make zero study decisions; this module makes
all of them.

Two halves:

- next_question(student): pick the next fact to show (due learning steps,
  then due reviews, then introduce new facts in stage order when the
  working set has room, with an occasional mastered fact sprinkled in).
- apply_answer(progress, ...): Leitner-style box movement, scaffold fading,
  due-date scheduling, mastery detection, and daily points.

Everything takes `now` so tests can drive the clock.
"""

import random
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import Fact, FactProgress, Student

# Box -> next interval. Boxes 0-1 are minute-scale "learning steps" within a
# session; 2+ are day-scale reviews.
INTERVALS = [
    timedelta(minutes=1),
    timedelta(minutes=10),
    timedelta(days=1),
    timedelta(days=2),
    timedelta(days=4),
    timedelta(days=8),
    timedelta(days=16),
    timedelta(days=32),
]
MAX_BOX = len(INTERVALS) - 1
LEARNING_BOX_MAX = 1   # boxes <= this are "learning" (working set)
MASTERY_BOX = 5

# "Fluent" thresholds, generous while a visual model is on screen (reading
# the model legitimately takes time) and tightening as it fades.
FLUENT_MS = {
    FactProgress.SCAFFOLD_FULL: 12000,
    FactProgress.SCAFFOLD_FADING: 9000,
    FactProgress.SCAFFOLD_NONE: 6000,
}
TARGET_MS = 5000           # the ultimate goal: unscaffolded answer under 5 s
SCAFFOLD_FADE_STREAK = 3   # fluent corrects needed to fade the model a level
WORKING_SET_MAX = 8        # don't introduce new facts past this many in-learning
MASTERED_MIX_PROB = 1 / 6  # chance of sprinkling in a mastered fact
WRONG_RETRY = timedelta(seconds=45)  # missed facts come back within the session
EMA_ALPHA = 0.3
MAX_RESPONSE_MS = 120000   # clamp: walked-away-from questions aren't 20-minute "answers"

# Daily-goal points: only answering earns anything, so idling is worthless
# and mashing wrong answers is worthless too.
POINTS_FLUENT = 3
POINTS_CORRECT = 2
POINTS_WRONG = 0


def next_question(student: Student, exclude_fact_id=None, now=None) -> FactProgress:
    """Pick the next FactProgress to drill (creating one if a new fact is
    being introduced). Never returns the same fact twice in a row unless
    it is literally the only option."""
    now = now or timezone.now()
    not_last = ~Q(fact_id=exclude_fact_id) if exclude_fact_id else Q()
    base = FactProgress.objects.filter(student=student).select_related('fact')

    # 1. Due learning steps (minute-scale): keep the working set moving.
    prog = (base.filter(not_last, box__lte=LEARNING_BOX_MAX, due_at__lte=now)
            .order_by('due_at').first())
    if prog:
        return prog

    # 2. Occasionally resurface a mastered fact (retention + confidence).
    if random.random() < MASTERED_MIX_PROB:
        prog = base.filter(not_last, mastered=True).order_by('?').first()
        if prog:
            return prog

    # 3. Due reviews, weakest and most overdue first.
    prog = (base.filter(not_last, box__gt=LEARNING_BOX_MAX, due_at__lte=now)
            .order_by('box', 'due_at').first())
    if prog:
        return prog

    # 4. Introduce a new fact if the working set has room.
    working = base.filter(box__lte=LEARNING_BOX_MAX, mastered=False).count()
    if working < WORKING_SET_MAX:
        fact = _next_new_fact(student)
        if fact:
            return FactProgress.objects.create(
                student=student, fact=fact, due_at=now, introduced_at=now)

    # 5. Nothing due and no room/new facts: practice ahead — soonest due.
    prog = base.filter(not_last).order_by('due_at').first()
    if prog:
        return prog
    # Brand-new student whose only progress row is the excluded fact, or
    # truly empty DB: fall back without the exclusion.
    prog = base.order_by('due_at').first()
    if prog:
        return prog
    fact = _next_new_fact(student)
    if fact:
        return FactProgress.objects.create(
            student=student, fact=fact, due_at=now, introduced_at=now)
    raise Fact.DoesNotExist('No facts seeded — run manage.py seed_facts')


def _next_new_fact(student: Student):
    """Next unseen fact in stage order; the commutative partner of the most
    recently introduced addition fact jumps the queue (cheap transfer)."""
    seen = FactProgress.objects.filter(student=student)
    last = seen.order_by('-introduced_at', '-id').select_related('fact').first()
    if last and last.fact.operation == 'add' and last.fact.a != last.fact.b:
        partner = Fact.objects.filter(
            operation='add', a=last.fact.b, b=last.fact.a).first()
        if partner and not seen.filter(fact=partner).exists():
            return partner
    return (Fact.objects
            .exclude(id__in=seen.values('fact_id'))
            .order_by('stage', 'operation', 'a', 'b')
            .first())


def apply_answer(progress: FactProgress, correct: bool, response_ms: int, now=None):
    """Update SRS state for one answer. Returns (points, mastered_now)."""
    now = now or timezone.now()
    response_ms = max(1, min(int(response_ms), MAX_RESPONSE_MS))
    fluent = correct and response_ms <= FLUENT_MS[progress.scaffold]

    if progress.ema_ms is None:
        progress.ema_ms = response_ms
    else:
        progress.ema_ms = int(EMA_ALPHA * response_ms + (1 - EMA_ALPHA) * progress.ema_ms)

    if correct:
        progress.streak += 1
        if fluent:
            progress.box = min(progress.box + 1, MAX_BOX)
            progress.due_at = now + INTERVALS[progress.box]
            progress.scaffold_streak += 1
            if (progress.scaffold > FactProgress.SCAFFOLD_NONE
                    and progress.scaffold_streak >= SCAFFOLD_FADE_STREAK):
                progress.scaffold -= 1
                progress.scaffold_streak = 0
        else:
            # Right but slow: don't advance, come back a step sooner.
            progress.due_at = now + INTERVALS[max(progress.box - 1, 0)]
            progress.scaffold_streak = 0
        points = POINTS_FLUENT if fluent else POINTS_CORRECT
    else:
        progress.streak = 0
        progress.lapses += 1
        progress.box = max(progress.box - 2, 0)
        progress.scaffold = min(progress.scaffold + 1, FactProgress.SCAFFOLD_FULL)
        progress.scaffold_streak = 0
        progress.due_at = now + WRONG_RETRY
        points = POINTS_WRONG

    was_mastered = progress.mastered
    progress.mastered = (
        progress.box >= MASTERY_BOX
        and progress.scaffold == FactProgress.SCAFFOLD_NONE
        and progress.ema_ms is not None
        and progress.ema_ms <= TARGET_MS
    )
    progress.save()
    return points, (progress.mastered and not was_mastered)
