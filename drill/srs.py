"""
The scheduling brain. Students make zero study decisions; this module makes
all of them.

Two halves:

- next_question(student): pick the next fact to show (due learning steps,
  then due reviews, then introduce new facts in stage order when the
  working set has room, with an occasional mastered fact sprinkled in).
  Everything is restricted to the operations the student is assigned
  (`Student.operations`, set by a teacher) — a fact from a switched-off
  operation is never served, even if the student has progress on it.
- apply_answer(progress, ...): Leitner-style box movement, scaffold fading,
  due-date scheduling, mastery detection, daily points, and the placement
  ladder below.

**Placement.** A student handed this app is not necessarily a beginner, and
marching them through every batch to find that out wastes hundreds of
questions. Two things avoid it:

- A fact answered correctly *and* fast on its very first exposure is taken as
  already known (`FactProgress.known_on_sight`): it skips most of the ladder,
  leaving the working set after one confirming review instead of six.
- `Student.reach` is the batch new facts are drawn from, and it moves with the
  evidence — up when a new fact turns out to be known, down when one is
  missed. So a fluent student climbs toward their actual frontier in about as
  many questions as there are batches, and a beginner stays put.

Coverage is not sacrificed to that: `FILL_IN_PROB` of introductions come from
the shallowest batch that still has unseen facts, so every fact is eventually
tested individually however high `reach` climbs.

Everything takes `now` so tests can drive the clock.
"""

import random
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import Fact, FactProgress, Student
from .strategies import STAGE_LABELS

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

# "Fluent" thresholds — deliberately forgiving early and tightening only as
# the fact is learned and its visual model fades. A brand-new fact (full
# model) gives 20 s; once the model is gone we close in on the 5 s goal.
# The practice UI's pace bar is driven by these exact numbers (see api_next),
# so what the student sees draining is the real window — never a shorter lie.
FLUENT_MS = {
    FactProgress.SCAFFOLD_FULL: 20000,
    FactProgress.SCAFFOLD_FADING: 11000,
    FactProgress.SCAFFOLD_NONE: 6000,
}
TARGET_MS = 5000           # the ultimate goal: unscaffolded answer under 5 s
SCAFFOLD_FADE_STREAK = 3   # fluent corrects needed to fade the model a level
WORKING_SET_MAX = 8        # don't introduce new facts past this many in-learning
MASTERED_MIX_PROB = 1 / 6  # chance of sprinkling in a mastered fact
WRONG_RETRY = timedelta(seconds=45)  # missed facts come back within the session
EMA_ALPHA = 0.3
MAX_RESPONSE_MS = 120000   # clamp: walked-away-from questions aren't 20-minute "answers"

# --- placement (see the module docstring)
# A first-ever answer this fast and correct is recall, not working it out — even
# with the visual model on screen. Deliberately the unscaffolded target rather
# than the generous FLUENT_MS for a brand-new fact: the point is to catch facts
# the student already owns, not to reward a quick count.
FIRST_SIGHT_MS = TARGET_MS
# Where a known-on-sight fact lands: one box short of mastery, so a single
# confirming review days later finishes it. One fast answer is evidence, not
# proof, so it never masters a fact outright.
KNOWN_BOX = MASTERY_BOX - 1
REACH_STEP = 1             # batches the ladder moves per piece of evidence
FILL_IN_PROB = 1 / 4       # introductions taken from the shallowest unseen batch

# A fact the student simply cannot do yet must not become the whole session.
# Left alone, a missed fact comes back every WRONG_RETRY, and four of them at
# minute-scale saturate the queue: the student grinds the same four forever,
# meets no new facts, and the app stops testing anything else. The miss that
# takes a fact's lapse count to LEECH_LAPSES rests it for a day instead of
# retrying it, which frees the rotation — it still comes back, just not on a
# loop.
LEECH_LAPSES = 5
LEECH_REST = timedelta(days=1)
# Only facts due inside this window are "in rotation" for WORKING_SET_MAX. A
# rested fact is still in a learning box but must not block new introductions,
# or coverage stalls behind the facts the student is stuck on.
WORKING_HORIZON = timedelta(hours=1)
# Resting leeches solves the grind but creates the opposite problem: once the
# facts a student is stuck on are all rested, practice drifts back to what they
# already know and the hard spots disappear from the session. So a share of
# questions deliberately revisits a struggling fact whether or not it is due.
# Sampled from a pool rather than always the single worst, so it is a rotation
# and not the same fact over and over.
STRUGGLE_MIX_PROB = 1 / 4
STRUGGLE_POOL = 12
# Relief. `Student.recent_misses` rises on a miss and falls on a correct
# answer; past RELIEF_AT the scheduler starts handing back facts the student
# can do. Without this, a student parked on their frontier answers most
# questions wrong — correct placement, useless practice, and no child sits
# through it. RELIEF_MAX caps the counter so one bad patch doesn't buy an
# indefinitely easy ride.
RELIEF_AT = 3
RELIEF_PROB = 1 / 2
RELIEF_MAX = 6

# Daily-goal points: only answering earns anything, so idling is worthless
# and mashing wrong answers is worthless too.
POINTS_FLUENT = 3
POINTS_CORRECT = 2
POINTS_WRONG = 0


def next_question(student: Student, exclude_fact_id=None, now=None) -> FactProgress:
    """Pick the next FactProgress to drill (creating one if a new fact is
    being introduced). Never returns the same fact twice in a row unless
    it is literally the only option. Only the student's enabled operations
    are considered."""
    now = now or timezone.now()
    ops = student.enabled_operations
    not_last = ~Q(fact_id=exclude_fact_id) if exclude_fact_id else Q()
    base = (FactProgress.objects.filter(student=student, fact__operation__in=ops)
            .select_related('fact'))

    # 1. A run of misses: deliberately give the student something they can do.
    #    This pre-empts even a due learning step — the run is the problem.
    if student.recent_misses >= RELIEF_AT and random.random() < RELIEF_PROB:
        prog = (base.filter(not_last, mastered=True).order_by('?').first()
                or base.filter(not_last, known_on_sight=True).order_by('?').first()
                or base.filter(not_last, box__gte=MASTERY_BOX).order_by('?').first())
        if prog:
            return prog

    # 2. Due learning steps (minute-scale): keep the working set moving.
    prog = (base.filter(not_last, box__lte=LEARNING_BOX_MAX, due_at__lte=now)
            .order_by('due_at').first())
    if prog:
        return prog

    # 3. Deliberately revisit something the student struggles with, due or not.
    #    This is what keeps the hard spots present once they have been rested;
    #    the pool means it rotates instead of hammering one fact.
    if random.random() < STRUGGLE_MIX_PROB:
        pool = list(base.filter(not_last, mastered=False, lapses__gt=0)
                    .order_by('-lapses', 'box')[:STRUGGLE_POOL])
        if pool:
            return random.choice(pool)

    # 4. Occasionally resurface a mastered fact (retention + confidence).
    if random.random() < MASTERED_MIX_PROB:
        prog = base.filter(not_last, mastered=True).order_by('?').first()
        if prog:
            return prog

    # 5. Due reviews, weakest and most overdue first.
    prog = (base.filter(not_last, box__gt=LEARNING_BOX_MAX, due_at__lte=now)
            .order_by('box', 'due_at').first())
    if prog:
        return prog

    # 6. Introduce a new fact if the working set has room. "Room" counts only
    #    facts actually in rotation — a rested leech is still in a learning
    #    box, and letting it hold a slot would stall coverage behind the very
    #    facts the student can't do.
    working = base.filter(box__lte=LEARNING_BOX_MAX, mastered=False,
                          due_at__lte=now + WORKING_HORIZON).count()
    if working < WORKING_SET_MAX:
        fact = _next_new_fact(student, ops)
        if fact:
            return FactProgress.objects.create(
                student=student, fact=fact, due_at=now, introduced_at=now)

    # 7. Nothing due and no room/new facts: practice ahead. Weakest first
    #    (lowest box, most lapses) rather than soonest-due, so an idle moment
    #    goes on the facts the student is actually struggling with.
    prog = (base.filter(not_last, mastered=False)
            .order_by('box', '-lapses', 'due_at').first())
    if prog:
        return prog
    prog = base.filter(not_last).order_by('due_at').first()
    if prog:
        return prog
    # Brand-new student whose only progress row is the excluded fact, or
    # truly empty DB: fall back without the exclusion.
    prog = base.order_by('due_at').first()
    if prog:
        return prog
    fact = _next_new_fact(student, ops)
    if fact:
        return FactProgress.objects.create(
            student=student, fact=fact, due_at=now, introduced_at=now)
    raise Fact.DoesNotExist(
        'No facts available for operations %s — run manage.py seed_facts' % ops)


def next_custom(student: Student, fact_ids, exclude_fact_id=None, now=None):
    """Pick the next fact for self-selected practice: only from `fact_ids`,
    weakest first (untested counts as weakest), never the same fact twice in a
    row unless it's the only one chosen. Creates a progress row on first use so
    the visual scaffold works. Facts from operations the student is no longer
    assigned are dropped, so an old selection can't reintroduce them."""
    now = now or timezone.now()
    ids = [int(i) for i in fact_ids]
    if not ids:
        raise Fact.DoesNotExist('empty custom selection')
    ids = list(Fact.objects.filter(
        id__in=ids, operation__in=student.enabled_operations
    ).values_list('id', flat=True))
    if not ids:
        raise Fact.DoesNotExist(
            'custom selection has no facts in the assigned operations')
    pool = [i for i in ids if i != exclude_fact_id] or ids
    progs = {p.fact_id: p for p in
             FactProgress.objects.filter(student=student, fact_id__in=pool)
             .select_related('fact')}

    def weakness(fid):
        p = progs.get(fid)
        box = -1 if p is None else p.box          # untested = weakest
        due = now if p is None else p.due_at
        return (box, due)

    chosen = min(pool, key=weakness)
    prog = progs.get(chosen)
    if prog is None:
        fact = Fact.objects.get(id=chosen)
        prog = FactProgress.objects.create(
            student=student, fact=fact, due_at=now, introduced_at=now)
    return prog


# How wide a slice of the current batch a new fact is drawn from. The batch is
# already scattered (strategies._order_batch), so this is what adds *per
# student* variety on top of that — two students working the same batch don't
# meet it in the same order. Wide is safe: a batch is homogeneous by
# construction, so anything in it is fair game once the batch is reached.
NEW_FACT_WINDOW = 16


# Operations where a x b and b x a are the same fact, so meeting one is a
# near-free head start on the other. (Subtraction and division don't commute.)
COMMUTATIVE_OPS = ('add', 'mul')


def _next_new_fact(student: Student, operations):
    """Introduce a new fact from one of `operations`.

    The batch comes from the placement ladder (`Student.reach`) rather than
    always being the shallowest unseen one, so a student who already knows the
    easy facts is not walked through them. `FILL_IN_PROB` of the time it is the
    shallowest unseen batch instead, which is what guarantees every fact is
    eventually tested however high `reach` has climbed.

    Within the chosen batch we pick randomly from a window of unseen facts
    (NEW_FACT_WINDOW), preferring answers the student isn't already drilling.
    The commutative partner of the most recently introduced
    addition/multiplication fact still jumps the queue (cheap transfer).
    """
    seen = FactProgress.objects.filter(student=student)
    last = (seen.filter(fact__operation__in=operations)
            .order_by('-introduced_at', '-id').select_related('fact').first())
    if (last and last.fact.operation in COMMUTATIVE_OPS
            and last.fact.a != last.fact.b):
        partner = Fact.objects.filter(
            operation=last.fact.operation, a=last.fact.b, b=last.fact.a).first()
        if partner and not seen.filter(fact=partner).exists():
            return partner
    unseen = (Fact.objects.filter(operation__in=operations)
              .exclude(id__in=seen.values('fact_id')).order_by('intro_order'))
    stage = _introduction_stage(student, unseen)
    if stage is None:
        return None
    window = list(unseen.filter(stage=stage)[:NEW_FACT_WINDOW])
    # Prefer an answer the student isn't already drilling. The batch order is
    # scattered so consecutive *introductions* differ, but the working set is
    # only ~8 facts and gets revisited all session — without this it can fill
    # up with several ways of making 13 (6+7, 7+6, 8+5, 5+8) and the session
    # feels like one long run of 13s even though the sequence is varied.
    busy = set(FactProgress.objects
               .filter(student=student, box__lte=LEARNING_BOX_MAX, mastered=False)
               .values_list('fact__answer', flat=True))
    fresh = [f for f in window if f.answer not in busy]
    return random.choice(fresh or window)


def _introduction_stage(student: Student, unseen):
    """Which batch to introduce from, given the batches that still have unseen
    facts for this student's operations. Returns None when nothing is left.

    `reach` is a *target*, not an index: it is clamped to the batches that
    actually still have unseen facts, so it can point past a batch the student
    has exhausted (or below one they never had, e.g. a multiplication-only
    student whose reach still reads 1).
    """
    stages = sorted(unseen.values_list('stage', flat=True).distinct())
    if not stages:
        return None
    if random.random() < FILL_IN_PROB:
        return stages[0]            # coverage: the oldest unfinished batch
    # the deepest batch at or below reach, else the shallowest one left
    at_or_below = [s for s in stages if s <= student.reach]
    return at_or_below[-1] if at_or_below else stages[0]


def _update_student_model(progress: FactProgress, correct, known, first_sight):
    """Fold this answer into what the scheduler believes about the student: the
    relief counter every time, and the placement ladder on a first answer.
    One save for both."""
    student = progress.student
    before = (student.reach, student.recent_misses)
    if correct:
        student.recent_misses = max(0, student.recent_misses - 1)
    else:
        student.recent_misses = min(RELIEF_MAX, student.recent_misses + 1)
    if first_sight:
        student.reach = _next_reach(student.reach, progress.fact.stage,
                                    known=known, correct=correct)
    if (student.reach, student.recent_misses) != before:
        student.save(update_fields=['reach', 'recent_misses'])


def _next_reach(reach, stage, known: bool, correct: bool):
    """Nudge the placement ladder after a *first* answer to a new fact.

    Up when the fact turned out to be already known, down when it was missed,
    and held where it is when the student got it but had to work — that last
    case is the level we want them at, so it is the stable point.

    Moves are relative to the batch the fact came from, not to `reach` itself:
    a fill-in fact from batch 2 getting missed should not drag a reach of 11
    down to 10, but it should stop reach running further ahead.

    A miss settles reach *on* that batch rather than below it. Missing a fact
    in batch 5 means batch 5 is where the learning is; retreating to 4 would
    spend the student's time on facts they have already shown they know, and
    they will be pushed back up anyway by the next known-on-sight fact.
    """
    if known:
        target = max(reach, stage + REACH_STEP)
    elif not correct:
        target = min(reach, stage)
    else:
        return reach
    return max(1, min(target, max(STAGE_LABELS)))


def apply_answer(progress: FactProgress, correct: bool, response_ms: int, now=None):
    """Update SRS state for one answer. Returns (points, mastered_now).

    Also moves the student's placement ladder on a fact's *first* answer — the
    scheduler updating its estimate of the student, which is why this touches
    Student as well as FactProgress.
    """
    now = now or timezone.now()
    response_ms = max(1, min(int(response_ms), MAX_RESPONSE_MS))
    fluent = correct and response_ms <= FLUENT_MS[progress.scaffold]
    # ema_ms is None exactly until the first answer lands
    first_sight = progress.ema_ms is None
    known_now = first_sight and correct and response_ms <= FIRST_SIGHT_MS

    if progress.ema_ms is None:
        progress.ema_ms = response_ms
    else:
        progress.ema_ms = int(EMA_ALPHA * response_ms + (1 - EMA_ALPHA) * progress.ema_ms)

    if known_now:
        # Already known: skip the ladder instead of drilling it six more times.
        # One confirming review at KNOWN_BOX's interval finishes the fact.
        progress.known_on_sight = True
        progress.scaffold = FactProgress.SCAFFOLD_NONE
        progress.scaffold_streak = 0
        progress.box = KNOWN_BOX
        progress.streak = 1
        progress.due_at = now + INTERVALS[KNOWN_BOX]
        points = POINTS_FLUENT
    elif correct:
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
        # a fact missed this often is rested, not retried round and round
        progress.due_at = now + (LEECH_REST if progress.lapses >= LEECH_LAPSES
                                 else WRONG_RETRY)
        points = POINTS_WRONG

    was_mastered = progress.mastered
    progress.mastered = (
        progress.box >= MASTERY_BOX
        and progress.scaffold == FactProgress.SCAFFOLD_NONE
        and progress.ema_ms is not None
        and progress.ema_ms <= TARGET_MS
    )
    progress.save()

    _update_student_model(progress, correct=correct, known=known_now,
                          first_sight=first_sight)
    return points, (progress.mastered and not was_mastered)
