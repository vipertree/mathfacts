from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from drill import srs
from drill.models import Fact, FactProgress, Student


def make_student(username='kid'):
    user = User.objects.create_user(username=username, password='pw')
    return Student.objects.create(user=user)


def seed():
    from django.core.management import call_command
    call_command('seed_facts', verbosity=0)


class ApplyAnswerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()

    def setUp(self):
        self.student = make_student()
        self.now = timezone.now()
        self.prog = FactProgress.objects.create(
            student=self.student, fact=Fact.objects.first(),
            due_at=self.now, introduced_at=self.now)

    def answer(self, correct=True, ms=2000):
        return srs.apply_answer(self.prog, correct, ms, now=self.now)

    def seen_already(self, ms=9000):
        """Take the fixture past its first exposure. The placement fast-track
        fires only on a fact's *first* answer, so tests about the ordinary
        ladder have to start from a fact that has already been met."""
        self.prog.ema_ms = ms
        self.prog.save()

    def test_fluent_correct_advances_box_and_schedules(self):
        self.seen_already()
        points, mastered = self.answer(correct=True, ms=2000)
        self.assertEqual(self.prog.box, 1)
        self.assertEqual(self.prog.due_at, self.now + srs.INTERVALS[1])
        self.assertEqual(points, srs.POINTS_FLUENT)
        self.assertFalse(mastered)

    def test_slow_correct_does_not_advance(self):
        self.prog.box = 3
        points, _ = self.answer(correct=True, ms=30000)
        self.assertEqual(self.prog.box, 3)
        self.assertEqual(points, srs.POINTS_CORRECT)
        # comes back sooner than the full box-3 interval
        self.assertEqual(self.prog.due_at, self.now + srs.INTERVALS[2])

    def test_wrong_drops_two_boxes_and_raises_scaffold(self):
        self.prog.box = 4
        self.prog.scaffold = FactProgress.SCAFFOLD_NONE
        points, _ = self.answer(correct=False)
        self.assertEqual(self.prog.box, 2)
        self.assertEqual(self.prog.scaffold, FactProgress.SCAFFOLD_FADING)
        self.assertEqual(points, srs.POINTS_WRONG)
        self.assertEqual(self.prog.due_at, self.now + srs.WRONG_RETRY)
        self.assertEqual(self.prog.lapses, 1)

    def test_wrong_box_floors_at_zero(self):
        self.prog.box = 1
        self.answer(correct=False)
        self.assertEqual(self.prog.box, 0)

    def test_scaffold_fades_after_three_fluent_corrects(self):
        self.seen_already()
        self.assertEqual(self.prog.scaffold, FactProgress.SCAFFOLD_FULL)
        for _ in range(3):
            self.answer(correct=True, ms=2000)
        self.assertEqual(self.prog.scaffold, FactProgress.SCAFFOLD_FADING)
        self.assertEqual(self.prog.scaffold_streak, 0)
        for _ in range(3):
            self.answer(correct=True, ms=2000)
        self.assertEqual(self.prog.scaffold, FactProgress.SCAFFOLD_NONE)

    def test_fluency_threshold_loosens_with_scaffold(self):
        # 10s is fluent with a full visual model (12s allowed)…
        self.prog.scaffold = FactProgress.SCAFFOLD_FULL
        points, _ = self.answer(correct=True, ms=10000)
        self.assertEqual(points, srs.POINTS_FLUENT)
        # …but not without one (6s allowed)
        self.prog.scaffold = FactProgress.SCAFFOLD_NONE
        points, _ = self.answer(correct=True, ms=10000)
        self.assertEqual(points, srs.POINTS_CORRECT)

    def test_mastery_requires_box_scaffold_and_speed(self):
        self.prog.box = srs.MASTERY_BOX - 1
        self.prog.scaffold = FactProgress.SCAFFOLD_NONE
        self.prog.ema_ms = 2000
        _, mastered_now = self.answer(correct=True, ms=2000)
        self.assertTrue(mastered_now)
        self.assertTrue(self.prog.mastered)
        # only reported as new once
        _, mastered_now = self.answer(correct=True, ms=2000)
        self.assertFalse(mastered_now)

    def test_no_mastery_while_slow(self):
        self.prog.box = srs.MAX_BOX
        self.prog.scaffold = FactProgress.SCAFFOLD_NONE
        self.prog.ema_ms = 9000
        self.answer(correct=True, ms=5900)  # fluent but ema stays above 5s
        self.assertFalse(self.prog.mastered)

    def test_ema_smoothing(self):
        self.prog.ema_ms = None
        self.answer(correct=True, ms=4000)
        self.assertEqual(self.prog.ema_ms, 4000)
        self.answer(correct=True, ms=2000)
        self.assertEqual(self.prog.ema_ms, int(0.3 * 2000 + 0.7 * 4000))

    def test_response_time_clamped(self):
        self.answer(correct=True, ms=10**9)
        self.assertEqual(self.prog.ema_ms, srs.MAX_RESPONSE_MS)


class NextQuestionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()

    def setUp(self):
        self.student = make_student()
        self.now = timezone.now()

    def test_brand_new_student_gets_stage_one_fact(self):
        prog = srs.next_question(self.student, now=self.now)
        self.assertEqual(prog.fact.stage, 1)
        self.assertEqual(prog.box, 0)

    def test_introduction_is_randomized_within_the_batch(self):
        # the first introduced fact stays in batch 1 but varies between
        # students (not a rigid, identical sequence for everyone)
        firsts = set()
        for i in range(20):
            s = make_student(f'kid{i}')
            prog = srs.next_question(s, now=self.now)
            self.assertEqual(prog.fact.stage, 1)
            firsts.add(prog.fact_id)
        self.assertGreater(len(firsts), 1)

    def test_commutative_partner_introduced_next(self):
        first = srs.next_question(self.student, now=self.now)
        # push the first fact out of "due" so introduction logic runs again
        first.due_at = self.now + timedelta(days=1)
        first.save()
        if first.fact.a != first.fact.b:
            second = srs.next_question(
                self.student, exclude_fact_id=first.fact_id, now=self.now)
            self.assertEqual(second.fact.a, first.fact.b)
            self.assertEqual(second.fact.b, first.fact.a)

    def test_due_learning_step_beats_introduction(self):
        prog = srs.next_question(self.student, now=self.now)
        again = srs.next_question(self.student, now=self.now + timedelta(minutes=5))
        self.assertEqual(again.fact_id, prog.fact_id)

    def test_never_same_fact_twice_in_a_row(self):
        prog = srs.next_question(self.student, now=self.now)
        nxt = srs.next_question(
            self.student, exclude_fact_id=prog.fact_id, now=self.now)
        self.assertNotEqual(nxt.fact_id, prog.fact_id)

    def test_working_set_caps_introductions(self):
        # "room" counts facts in rotation, i.e. due inside WORKING_HORIZON — a
        # rested fact is still in a learning box but must not hold a slot, or
        # coverage stalls behind whatever the student is stuck on
        soon = self.now + srs.WORKING_HORIZON - timedelta(minutes=1)
        for _ in range(srs.WORKING_SET_MAX):
            prog = srs.next_question(self.student, now=self.now)
            prog.box = 0
            prog.due_at = soon
            prog.save()
        count_before = FactProgress.objects.filter(student=self.student).count()
        self.assertEqual(count_before, srs.WORKING_SET_MAX)
        # working set full of in-rotation facts -> no new fact is introduced
        srs.next_question(self.student, now=self.now)
        self.assertEqual(
            FactProgress.objects.filter(student=self.student).count(), count_before)

    def test_rested_facts_do_not_block_introductions(self):
        # the regression this guards: a student stuck on a handful of facts met
        # 17 of 693 facts in 400 questions, because the facts they could not do
        # held every working-set slot for ever
        for _ in range(srs.WORKING_SET_MAX):
            prog = srs.next_question(self.student, now=self.now)
            prog.box = 0
            prog.due_at = self.now + srs.LEECH_REST      # rested, not in rotation
            prog.save()
        count_before = FactProgress.objects.filter(student=self.student).count()
        srs.next_question(self.student, now=self.now)
        self.assertEqual(
            FactProgress.objects.filter(student=self.student).count(),
            count_before + 1)

    def test_due_review_selected(self):
        prog = srs.next_question(self.student, now=self.now)
        prog.box = 3
        prog.due_at = self.now - timedelta(hours=1)
        prog.save()
        # use a "now" where nothing else exists; review must surface
        chosen = srs.next_question(self.student, now=self.now)
        self.assertEqual(chosen.fact_id, prog.fact_id)

    def test_empty_fact_table_raises(self):
        Fact.objects.all().delete()
        with self.assertRaises(Fact.DoesNotExist):
            srs.next_question(self.student, now=self.now)
