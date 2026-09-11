"""Placement: finding out what a student already knows, fast.

The problem these cover: a student handed this app is not necessarily a
beginner, and walking them batch by batch to discover that wastes hundreds of
questions. Three mechanisms, each with its own failure mode to guard against:

- `known_on_sight` fast-tracks a fact answered right and fast first time.
- `Student.reach` is a placement ladder: up when a new fact turns out to be
  known, down onto the batch where one is missed.
- leech resting + the struggle mix keep the two opposite failures away — a
  handful of impossible facts eating every question, and the hard facts
  disappearing from the session once rested.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from drill import srs
from drill.models import Fact, FactProgress, Student
from drill.strategies import STAGE_LABELS, stage_for


def make_student(username='kid', operations=None, reach=1):
    user = User.objects.create_user(username=username, password='pw')
    return Student.objects.create(
        user=user, reach=reach,
        operations=list(operations) if operations else ['add', 'sub'])


class FirstSightTests(TestCase):
    """A fact answered right and fast first time is treated as already known."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def setUp(self):
        self.student = make_student()
        self.now = timezone.now()
        self.fact = Fact.objects.filter(stage=1).first()

    def new_progress(self):
        return FactProgress.objects.create(
            student=self.student, fact=self.fact,
            due_at=self.now, introduced_at=self.now)

    def test_fast_correct_first_answer_skips_most_of_the_ladder(self):
        prog = self.new_progress()
        points, mastered = srs.apply_answer(prog, True, 1500, now=self.now)
        self.assertTrue(prog.known_on_sight)
        self.assertEqual(prog.box, srs.KNOWN_BOX)
        self.assertEqual(prog.scaffold, FactProgress.SCAFFOLD_NONE)
        self.assertEqual(prog.due_at, self.now + srs.INTERVALS[srs.KNOWN_BOX])
        self.assertEqual(points, srs.POINTS_FLUENT)
        # evidence, not proof: one fast answer never masters a fact outright
        self.assertFalse(mastered)
        self.assertFalse(prog.mastered)

    def test_one_confirming_review_then_masters(self):
        # the payoff: two exposures for a known fact instead of six
        prog = self.new_progress()
        srs.apply_answer(prog, True, 1500, now=self.now)
        later = self.now + srs.INTERVALS[srs.KNOWN_BOX]
        _points, mastered_now = srs.apply_answer(prog, True, 1500, now=later)
        self.assertTrue(mastered_now)
        self.assertTrue(prog.mastered)

    def test_slow_correct_first_answer_is_not_taken_as_known(self):
        prog = self.new_progress()
        srs.apply_answer(prog, True, srs.FIRST_SIGHT_MS + 1, now=self.now)
        self.assertFalse(prog.known_on_sight)
        self.assertEqual(prog.box, 1)                       # the ordinary step
        self.assertEqual(prog.scaffold, FactProgress.SCAFFOLD_FULL)

    def test_wrong_first_answer_is_not_taken_as_known(self):
        prog = self.new_progress()
        srs.apply_answer(prog, False, 1500, now=self.now)
        self.assertFalse(prog.known_on_sight)
        self.assertEqual(prog.lapses, 1)

    def test_a_fast_answer_later_on_does_not_count_as_first_sight(self):
        prog = self.new_progress()
        srs.apply_answer(prog, False, 9000, now=self.now)   # met it, missed it
        srs.apply_answer(prog, True, 1000, now=self.now)    # now fast
        self.assertFalse(prog.known_on_sight)
        self.assertLess(prog.box, srs.KNOWN_BOX)


class ReachLadderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def setUp(self):
        self.now = timezone.now()

    def answer_a_new_fact(self, student, stage, correct, ms):
        fact = (Fact.objects.filter(stage=stage)
                .exclude(id__in=FactProgress.objects.filter(student=student)
                         .values('fact_id')).first())
        prog = FactProgress.objects.create(
            student=student, fact=fact, due_at=self.now, introduced_at=self.now)
        srs.apply_answer(prog, correct, ms, now=self.now)
        student.refresh_from_db()
        return prog

    def test_reach_climbs_when_a_new_fact_turns_out_to_be_known(self):
        student = make_student(reach=3)
        self.answer_a_new_fact(student, 3, correct=True, ms=1200)
        self.assertEqual(student.reach, 4)

    def test_reach_holds_when_the_student_had_to_work_for_it(self):
        # right but slow is exactly the level we want them at
        student = make_student(reach=5)
        self.answer_a_new_fact(student, 5, correct=True, ms=9000)
        self.assertEqual(student.reach, 5)

    def test_reach_settles_on_the_missed_batch_not_below_it(self):
        # missing a batch-5 fact means batch 5 is where the learning is;
        # retreating to 4 would drill facts already shown to be known
        student = make_student(reach=8)
        self.answer_a_new_fact(student, 5, correct=False, ms=9000)
        self.assertEqual(student.reach, 5)

    def test_a_miss_on_a_fill_in_fact_does_not_drag_reach_down(self):
        student = make_student(reach=11)
        self.answer_a_new_fact(student, 2, correct=False, ms=9000)
        self.assertEqual(student.reach, 2)   # settles on that batch
        # but a *known* fill-in never pulls a high reach backwards
        student.reach = 11
        student.save()
        self.answer_a_new_fact(student, 2, correct=True, ms=1000)
        self.assertEqual(student.reach, 11)

    def test_reach_only_moves_on_a_facts_first_answer(self):
        student = make_student(reach=4)
        prog = self.answer_a_new_fact(student, 4, correct=True, ms=9000)
        self.assertEqual(student.reach, 4)
        for _ in range(5):                       # more answers, same fact
            srs.apply_answer(prog, True, 1000, now=self.now)
        student.refresh_from_db()
        self.assertEqual(student.reach, 4)

    def test_reach_stays_inside_the_batch_range(self):
        student = make_student(reach=max(STAGE_LABELS),
                               operations=['add', 'sub', 'mul', 'div'])
        self.answer_a_new_fact(student, max(STAGE_LABELS), correct=True, ms=900)
        self.assertLessEqual(student.reach, max(STAGE_LABELS))
        student.reach = 1
        student.save()
        self.answer_a_new_fact(student, 1, correct=False, ms=9000)
        self.assertGreaterEqual(student.reach, 1)


class PlacementSpeedTests(TestCase):
    """The headline behaviour: how fast the app finds a student's frontier."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def play(self, student, knows, questions):
        """Answer `questions` questions: known facts fast and right, unknown
        ones wrong. Returns the list of batches actually asked about."""
        now = timezone.now()
        asked, last = [], None
        for _ in range(questions):
            prog = srs.next_question(student, exclude_fact_id=last, now=now)
            fact = prog.fact
            if knows(fact):
                srs.apply_answer(prog, True, 1500, now=now)
            else:
                srs.apply_answer(prog, False, 11000, now=now)
            student.refresh_from_db()
            asked.append(fact.stage)
            last = fact.id
            now += timedelta(seconds=12)
        return asked

    @staticmethod
    def knows_below(stage):
        return lambda f: stage_for(f.operation, f.a, f.b) < stage

    def test_a_student_fluent_to_batch_six_reaches_batch_seven_within_25_questions(self):
        # the point of the whole feature: not 36 batch-1 facts first
        student = make_student()
        asked = self.play(student, self.knows_below(7), 25)
        self.assertIn(7, asked, f'never got past {sorted(set(asked))}')
        self.assertEqual(student.reach, 7)

    def test_placement_lands_on_the_right_batch_for_several_abilities(self):
        for frontier in (3, 5, 7):
            student = make_student(f'kid{frontier}')
            self.play(student, self.knows_below(frontier), 40)
            self.assertEqual(
                student.reach, frontier,
                f'a student fluent below batch {frontier} placed at '
                f'{student.reach}')

    def test_a_beginner_is_left_at_the_beginning(self):
        student = make_student()
        asked = self.play(student, lambda f: False, 40)
        self.assertEqual(student.reach, 1)
        self.assertEqual(set(asked), {1}, 'a beginner was pushed past batch 1')

    def test_a_multiplication_only_student_places_inside_the_mul_batches(self):
        # reach still reads 1, which is not a multiplication batch at all: the
        # ladder is clamped to batches that have facts for these operations
        student = make_student(operations=['mul'])
        asked = self.play(student, self.knows_below(13), 30)
        self.assertTrue(set(asked) <= set(range(9, 15)), sorted(set(asked)))
        self.assertIn(13, asked)


class StuckStudentTests(TestCase):
    """Neither failure mode: grinding a handful of impossible facts, nor
    quietly dropping the hard ones once they have been rested."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def play(self, student, knows, questions):
        now = timezone.now()
        asked, last = [], None
        for _ in range(questions):
            prog = srs.next_question(student, exclude_fact_id=last, now=now)
            fact = prog.fact
            correct = knows(fact)
            srs.apply_answer(prog, correct, 1500 if correct else 11000, now=now)
            student.refresh_from_db()
            asked.append((fact.id, fact.stage, correct))
            last = fact.id
            now += timedelta(seconds=12)
        return asked

    def setUp(self):
        self.student = make_student()
        self.knows = lambda f: stage_for(f.operation, f.a, f.b) < 7

    def test_a_missed_fact_is_rested_rather_than_retried_for_ever(self):
        fact = Fact.objects.filter(stage=7).first()
        now = timezone.now()
        prog = FactProgress.objects.create(
            student=self.student, fact=fact, due_at=now, introduced_at=now)
        # the first few misses come straight back...
        for miss in range(1, srs.LEECH_LAPSES):
            srs.apply_answer(prog, False, 11000, now=now)
            self.assertEqual(prog.lapses, miss)
            self.assertEqual(prog.due_at, now + srs.WRONG_RETRY)
        # ...and the one that reaches LEECH_LAPSES is rested instead
        srs.apply_answer(prog, False, 11000, now=now)
        self.assertEqual(prog.lapses, srs.LEECH_LAPSES)
        self.assertEqual(prog.due_at, now + srs.LEECH_REST)

    def test_a_stuck_student_still_meets_plenty_of_facts(self):
        # regression: this was 17 facts in 400 questions, the same four on a
        # loop, because they held every working-set slot for ever.
        # Measured over 8 trials of this scenario: 33-41 facts met, 33-41
        # distinct facts asked. The threshold sits clear of that spread.
        asked = self.play(self.student, self.knows, 200)
        met = FactProgress.objects.filter(student=self.student).count()
        self.assertGreater(met, 25, f'only met {met} facts in 200 questions')
        distinct = len({fact_id for fact_id, _s, _c in asked})
        self.assertGreater(distinct, 25, f'only {distinct} distinct facts asked')

    def test_a_stuck_student_keeps_being_given_the_hard_facts(self):
        # regression: resting the leeches made the hard batch vanish entirely
        # from the second half of the session
        asked = self.play(self.student, self.knows, 200)
        tail = asked[len(asked) // 2:]
        hard = sum(1 for _id, _stage, correct in tail if not correct)
        share = hard / len(tail)
        # Measured 50-58% across 8 trials. Both bounds matter: too low and the
        # hard spots have dropped out of the session, too high and a child is
        # answering almost everything wrong and will stop trying.
        self.assertGreater(
            share, 0.15,
            f'only {share:.0%} of later questions were facts the student '
            f'cannot do — the hard spots dropped out of the session')
        self.assertLess(
            share, 0.80,
            f'{share:.0%} of later questions were facts the student cannot do '
            f'— that is a grind, not practice')

    def test_the_struggle_mix_rotates_instead_of_hammering_one_fact(self):
        # measured 19-23 distinct hard facts over 8 trials
        asked = self.play(self.student, self.knows, 200)
        hard_ids = [fact_id for fact_id, _s, correct in asked if not correct]
        self.assertGreater(len(set(hard_ids)), 10,
                           'the same few facts over and over')

    def test_struggling_facts_come_back_even_when_nothing_is_due(self):
        now = timezone.now()
        # one fact with lapses, parked far in the future; nothing else due
        hard = Fact.objects.filter(stage=7).first()
        FactProgress.objects.create(
            student=self.student, fact=hard, lapses=3, box=0,
            due_at=now + timedelta(days=5), introduced_at=now)
        easy = Fact.objects.filter(stage=1)[:4]
        for f in easy:
            FactProgress.objects.create(
                student=self.student, fact=f, box=srs.MAX_BOX, mastered=True,
                scaffold=0, ema_ms=1200, due_at=now + timedelta(days=20),
                introduced_at=now)
        with mock.patch('drill.srs.random.random', return_value=0.0):
            prog = srs.next_question(self.student, now=now)
        self.assertEqual(prog.fact_id, hard.id)


class ReliefTests(TestCase):
    """After a run of misses the scheduler hands back a fact the student can
    do. Placement that only escalates is how a child ends up answering almost
    everything wrong."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def setUp(self):
        self.student = make_student()
        self.now = timezone.now()

    def progress_for(self, stage, **kwargs):
        fact = (Fact.objects.filter(stage=stage)
                .exclude(id__in=FactProgress.objects.filter(student=self.student)
                         .values('fact_id')).first())
        return FactProgress.objects.create(
            student=self.student, fact=fact, due_at=self.now,
            introduced_at=self.now, **kwargs)

    def test_misses_raise_the_counter_and_correct_answers_lower_it(self):
        prog = self.progress_for(1)
        for expected in (1, 2, 3):
            srs.apply_answer(prog, False, 11000, now=self.now)
            self.student.refresh_from_db()
            self.assertEqual(self.student.recent_misses, expected)
        srs.apply_answer(prog, True, 1200, now=self.now)
        self.student.refresh_from_db()
        self.assertEqual(self.student.recent_misses, 2)

    def test_the_counter_is_capped(self):
        prog = self.progress_for(1)
        for _ in range(srs.RELIEF_MAX + 5):
            srs.apply_answer(prog, False, 11000, now=self.now)
        self.student.refresh_from_db()
        self.assertEqual(self.student.recent_misses, srs.RELIEF_MAX)

    def test_relief_serves_a_known_fact_over_a_due_hard_one(self):
        hard = self.progress_for(7, box=0, lapses=4)
        hard.due_at = self.now - timedelta(minutes=5)      # overdue
        hard.save()
        easy = self.progress_for(1, box=srs.MAX_BOX, mastered=True,
                                 scaffold=0, ema_ms=1200)
        easy.due_at = self.now + timedelta(days=10)        # nowhere near due
        easy.save()
        self.student.recent_misses = srs.RELIEF_AT
        self.student.save()
        with mock.patch('drill.srs.random.random', return_value=0.0):
            prog = srs.next_question(self.student, now=self.now)
        self.assertEqual(prog.fact_id, easy.fact_id)

    def test_no_relief_before_the_threshold(self):
        hard = self.progress_for(7, box=0, lapses=4)
        hard.due_at = self.now - timedelta(minutes=5)
        hard.save()
        self.progress_for(1, box=srs.MAX_BOX, mastered=True, scaffold=0,
                          ema_ms=1200)
        self.student.recent_misses = srs.RELIEF_AT - 1
        self.student.save()
        with mock.patch('drill.srs.random.random', return_value=0.0):
            prog = srs.next_question(self.student, now=self.now)
        self.assertEqual(prog.fact_id, hard.fact_id)

    def test_relief_is_skipped_when_there_is_nothing_easy_yet(self):
        # a true beginner has no wins banked; the scheduler must not stall
        hard = self.progress_for(1, box=0, lapses=4)
        hard.due_at = self.now - timedelta(minutes=5)
        hard.save()
        self.student.recent_misses = srs.RELIEF_MAX
        self.student.save()
        with mock.patch('drill.srs.random.random', return_value=0.0):
            prog = srs.next_question(self.student, now=self.now)
        self.assertIsNotNone(prog)


class CoverageTests(TestCase):
    """However high reach climbs, every fact is still eventually tested."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def test_fill_in_introductions_come_from_the_shallowest_unseen_batch(self):
        student = make_student(reach=8)
        unseen = Fact.objects.filter(operation__in=['add', 'sub'])
        with mock.patch('drill.srs.random.random', return_value=0.0):
            stage = srs._introduction_stage(student, unseen)
        self.assertEqual(stage, 1, 'fill-in did not reach back to batch 1')

    def test_without_fill_in_the_deepest_batch_at_or_below_reach_is_used(self):
        student = make_student(reach=6)
        unseen = Fact.objects.filter(operation__in=['add', 'sub'])
        with mock.patch('drill.srs.random.random', return_value=0.99):
            stage = srs._introduction_stage(student, unseen)
        self.assertEqual(stage, 6)

    def test_reach_beyond_the_available_batches_falls_back(self):
        student = make_student(operations=['mul'], reach=1)
        unseen = Fact.objects.filter(operation='mul')
        with mock.patch('drill.srs.random.random', return_value=0.99):
            stage = srs._introduction_stage(student, unseen)
        self.assertEqual(stage, 9, 'a mul-only student must start at batch 9')

    def test_no_unseen_facts_gives_no_stage(self):
        student = make_student()
        self.assertIsNone(
            srs._introduction_stage(student, Fact.objects.none()))

    def test_a_fluent_student_eventually_covers_the_easy_batches_too(self):
        student = make_student()
        now = timezone.now()
        last = None
        for _ in range(300):
            prog = srs.next_question(student, exclude_fact_id=last, now=now)
            srs.apply_answer(prog, True, 1500, now=now)
            student.refresh_from_db()
            last = prog.fact_id
            now += timedelta(seconds=12)
        met = FactProgress.objects.filter(student=student)
        self.assertEqual(met.filter(fact__stage=1).count(),
                         Fact.objects.filter(stage=1).count(),
                         'batch 1 was never finished off')
        self.assertGreater(student.reach, 1)


class PlacementIsVisibleTests(TestCase):
    """A placement the teacher can't see is a placement they can't trust."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def setUp(self):
        User.objects.create_user('teacher', password='pw', is_staff=True)
        self.client.login(username='teacher', password='pw')

    def test_manage_page_reports_where_each_student_is_working(self):
        student = make_student('kid', reach=7)
        response = self.client.get('/manage/')
        self.assertEqual(response.status_code, 200)
        row = next(r for r in response.context['rows']
                   if r['student'].pk == student.pk)
        self.assertEqual(row['working_on'], STAGE_LABELS[7])
        self.assertContains(response, STAGE_LABELS[7])

    def test_working_on_stays_inside_the_students_own_operations(self):
        # reach is clamped at introduction time, not stored clamped, so it can
        # point at a batch this student never practises
        student = make_student('timeskid', operations=['mul'], reach=3)
        row = next(r for r in self.client.get('/manage/').context['rows']
                   if r['student'].pk == student.pk)
        self.assertEqual(row['working_on'], STAGE_LABELS[9])

    def test_a_students_own_report_shows_it_too(self):
        make_student('kid', reach=5)
        self.client.login(username='kid', password='pw')
        response = self.client.get('/progress/')
        self.assertEqual(response.context['working_on'], STAGE_LABELS[5])
        self.assertContains(response, 'working on now')
