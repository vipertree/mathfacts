"""Per-student operation assignment: the four operations a teacher turns on
and off from the Manage students page, and everything downstream of that
choice (what the SRS serves, what the report shows, what the keypad allows).
"""
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from drill import srs
from drill.models import (DEFAULT_OPERATIONS, Fact, FactProgress, Student,
                          clean_operations)
from drill.strategies import answer_max, keypad_for


def seeded():
    call_command('seed_facts', verbosity=0)


def make_student(username='kid', operations=None):
    user = User.objects.create_user(username=username, password='pw')
    return Student.objects.create(
        user=user, operations=operations if operations is not None
        else list(DEFAULT_OPERATIONS))


class CleanOperationsTests(TestCase):
    def test_keeps_canonical_order_and_drops_junk(self):
        self.assertEqual(clean_operations(['div', 'add', 'mul']),
                         ['add', 'mul', 'div'])
        self.assertEqual(clean_operations(['add', 'add']), ['add'])
        self.assertEqual(clean_operations(['nonsense', 'sub']), ['sub'])
        self.assertEqual(clean_operations([]), [])
        self.assertEqual(clean_operations(None), [])

    def test_default_is_addition_and_subtraction(self):
        self.assertEqual(make_student().enabled_operations, ['add', 'sub'])

    def test_empty_or_broken_value_falls_back_to_the_default(self):
        # a student is never left with literally nothing to practice
        self.assertEqual(make_student('a', []).enabled_operations, ['add', 'sub'])
        self.assertEqual(
            make_student('b', ['garbage']).enabled_operations, ['add', 'sub'])

    def test_practices_helper(self):
        s = make_student(operations=['mul'])
        self.assertTrue(s.practices('mul'))
        self.assertFalse(s.practices('add'))


class SchedulerRespectsOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seeded()

    def setUp(self):
        self.now = timezone.now()

    def served_ops(self, student, rounds=40):
        """Answer `rounds` questions and report which operations came up."""
        ops, last = set(), None
        for _ in range(rounds):
            prog = srs.next_question(student, exclude_fact_id=last, now=self.now)
            ops.add(prog.fact.operation)
            srs.apply_answer(prog, True, 1000, now=self.now)
            last = prog.fact_id
        return ops

    def test_multiplication_only_student_never_sees_addition(self):
        student = make_student(operations=['mul'])
        self.assertEqual(self.served_ops(student), {'mul'})

    def test_multiplication_only_student_starts_at_the_first_mul_batch(self):
        student = make_student(operations=['mul'])
        prog = srs.next_question(student, now=self.now)
        self.assertEqual(prog.fact.operation, 'mul')
        self.assertEqual(prog.fact.stage, 9)   # x0/x1/x10, not addition's 1

    def test_division_only_student_gets_division(self):
        student = make_student(operations=['div'])
        # the opening batch first: answering everything correctly below would
        # climb the placement ladder past it
        self.assertEqual(srs.next_question(student, now=self.now).fact.stage, 15)
        self.assertEqual(self.served_ops(student), {'div'})

    def test_all_four_student_starts_in_addition(self):
        # everything on means the batches run in order, so a beginner still
        # starts where they should rather than being handed 7 x 8
        student = make_student(operations=['add', 'sub', 'mul', 'div'])
        prog = srs.next_question(student, now=self.now)
        self.assertEqual(prog.fact.operation, 'add')
        self.assertEqual(prog.fact.stage, 1)

    def test_all_four_student_moves_on_to_multiplication_once_add_sub_is_done(self):
        student = make_student(operations=['add', 'sub', 'mul', 'div'])
        # mastered every addition and subtraction fact, nothing due for weeks
        FactProgress.objects.bulk_create([
            FactProgress(student=student, fact=f, box=srs.MAX_BOX, mastered=True,
                         scaffold=FactProgress.SCAFFOLD_NONE, ema_ms=1500,
                         due_at=self.now + timedelta(days=30),
                         introduced_at=self.now - timedelta(days=60))
            for f in Fact.objects.filter(operation__in=['add', 'sub'])])
        # the scheduler also resurfaces a mastered fact 1-in-6 for retention,
        # which here would be an add/sub one — switch that off so this asserts
        # the introduction path rather than coming up heads
        with mock.patch.object(srs, 'MASTERED_MIX_PROB', 0):
            prog = srs.next_question(student, now=self.now)
        self.assertEqual(prog.fact.operation, 'mul')
        self.assertEqual(prog.fact.stage, 9)

    def test_turning_an_operation_off_stops_it_being_served(self):
        student = make_student(operations=['add', 'mul'])
        # give the student progress on a multiplication fact
        mul_fact = Fact.objects.filter(operation='mul').first()
        FactProgress.objects.create(
            student=student, fact=mul_fact,
            due_at=self.now - timedelta(days=1), introduced_at=self.now)
        student.operations = ['add']
        student.save()
        self.assertEqual(self.served_ops(student), {'add'})

    def test_progress_survives_being_switched_off_and_back_on(self):
        student = make_student(operations=['mul'])
        prog = srs.next_question(student, now=self.now)
        srs.apply_answer(prog, True, 1000, now=self.now)
        box_before, fact_id = prog.box, prog.fact_id
        self.assertGreater(box_before, 0)

        student.operations = ['add']
        student.save()
        self.assertEqual(self.served_ops(student), {'add'})
        # the multiplication row is untouched, not deleted
        kept = FactProgress.objects.get(student=student, fact_id=fact_id)
        self.assertEqual(kept.box, box_before)

        student.operations = ['mul']
        student.save()
        again = srs.next_question(student, now=self.now + timedelta(days=40))
        self.assertEqual(again.fact.operation, 'mul')

    def test_new_facts_avoid_answers_already_being_drilled(self):
        # the working set is small and revisited all session, so filling it
        # with 6+7, 7+6, 8+5, 5+8 makes a session feel like a run of 13s
        student = make_student(operations=['add'])
        answers = []
        for _ in range(srs.WORKING_SET_MAX):
            prog = srs.next_question(student, now=self.now)
            answers.append(prog.fact.answer)
            # park it so it is in-learning but not due, forcing another intro
            prog.due_at = self.now + timedelta(minutes=30)
            prog.save()
        # commutative partners legitimately share an answer, so pairs are fine
        # — what must not happen is the set collapsing onto a couple of answers
        self.assertGreaterEqual(
            len(set(answers)), srs.WORKING_SET_MAX // 2,
            f'working set answers were {answers}')

    def test_no_facts_for_the_assigned_operation_raises(self):
        student = make_student(operations=['div'])
        Fact.objects.filter(operation='div').delete()
        with self.assertRaises(Fact.DoesNotExist):
            srs.next_question(student, now=self.now)

    def test_commutative_partner_jumps_the_queue_for_multiplication(self):
        student = make_student(operations=['mul'])
        first = srs.next_question(student, now=self.now)
        first.due_at = self.now + timedelta(days=1)
        first.save()
        if first.fact.a != first.fact.b:
            second = srs.next_question(
                student, exclude_fact_id=first.fact_id, now=self.now)
            self.assertEqual((second.fact.a, second.fact.b),
                             (first.fact.b, first.fact.a))

    def test_division_has_no_commutative_shortcut(self):
        # 56/7 and 7/56 are not a pair; the partner rule must not fire
        self.assertNotIn('div', srs.COMMUTATIVE_OPS)
        self.assertNotIn('sub', srs.COMMUTATIVE_OPS)

    def test_custom_practice_drops_facts_outside_the_assignment(self):
        student = make_student(operations=['add'])
        mul_ids = list(Fact.objects.filter(operation='mul')
                       .values_list('id', flat=True)[:3])
        add_id = Fact.objects.filter(operation='add').first().id
        prog = srs.next_custom(student, mul_ids + [add_id], now=self.now)
        self.assertEqual(prog.fact_id, add_id)

    def test_custom_practice_with_only_disallowed_facts_raises(self):
        student = make_student(operations=['add'])
        mul_ids = list(Fact.objects.filter(operation='mul')
                       .values_list('id', flat=True)[:3])
        with self.assertRaises(Fact.DoesNotExist):
            srs.next_custom(student, mul_ids, now=self.now)


class ManageOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seeded()

    def setUp(self):
        User.objects.create_user('teacher', password='pw', is_staff=True)
        self.client.login(username='teacher', password='pw')

    def test_add_student_with_all_four_operations(self):
        response = self.client.post(reverse('manage'), {
            'action': 'add_student', 'username': 'newkid', 'password': 'pw12',
            'theme': 'pirate', 'goal': 150,
            'operations': ['add', 'sub', 'mul', 'div']})
        self.assertRedirects(response, reverse('manage'))
        student = Student.objects.get(user__username='newkid')
        self.assertEqual(student.enabled_operations,
                         ['add', 'sub', 'mul', 'div'])

    def test_add_student_with_only_multiplication(self):
        self.client.post(reverse('manage'), {
            'action': 'add_student', 'username': 'timeskid', 'password': 'pw12',
            'operations': ['mul']})
        student = Student.objects.get(user__username='timeskid')
        self.assertEqual(student.operations, ['mul'])

    def test_add_student_with_no_operations_is_rejected(self):
        response = self.client.post(reverse('manage'), {
            'action': 'add_student', 'username': 'nobody', 'password': 'pw12',
            'operations': []}, follow=True)
        self.assertFalse(User.objects.filter(username='nobody').exists())
        self.assertContains(response, 'at least one operation')

    def test_set_operations_updates_a_student(self):
        student = make_student('kid', ['add'])
        response = self.client.post(reverse('manage'), {
            'action': 'set_operations', 'student_id': student.pk,
            'operations': ['mul', 'div']}, follow=True)
        student.refresh_from_db()
        self.assertEqual(student.operations, ['mul', 'div'])
        self.assertContains(response, 'multiplication, division')

    def test_set_operations_accepts_any_single_operation(self):
        student = make_student('kid')
        for op in ('add', 'sub', 'mul', 'div'):
            self.client.post(reverse('manage'), {
                'action': 'set_operations', 'student_id': student.pk,
                'operations': [op]})
            student.refresh_from_db()
            self.assertEqual(student.operations, [op])

    def test_set_operations_ignores_unknown_codes(self):
        student = make_student('kid', ['add'])
        self.client.post(reverse('manage'), {
            'action': 'set_operations', 'student_id': student.pk,
            'operations': ['mul', 'algebra']})
        student.refresh_from_db()
        self.assertEqual(student.operations, ['mul'])

    def test_set_operations_refuses_to_leave_a_student_with_none(self):
        student = make_student('kid', ['mul'])
        response = self.client.post(reverse('manage'), {
            'action': 'set_operations', 'student_id': student.pk,
            'operations': []}, follow=True)
        student.refresh_from_db()
        self.assertEqual(student.operations, ['mul'])   # unchanged
        self.assertContains(response, 'at least one operation')

    def test_set_operations_prunes_a_stale_custom_selection(self):
        student = make_student('kid', ['add', 'mul'])
        add_ids = list(Fact.objects.filter(operation='add')
                       .values_list('id', flat=True)[:2])
        mul_ids = list(Fact.objects.filter(operation='mul')
                       .values_list('id', flat=True)[:2])
        student.custom_selection = add_ids + mul_ids
        student.save()
        self.client.post(reverse('manage'), {
            'action': 'set_operations', 'student_id': student.pk,
            'operations': ['add']})
        student.refresh_from_db()
        self.assertEqual(sorted(student.custom_selection), sorted(add_ids))

    def test_manage_page_shows_a_checkbox_per_operation_per_student(self):
        make_student('kid', ['add', 'mul'])
        response = self.client.get(reverse('manage'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for op in ('add', 'sub', 'mul', 'div'):
            self.assertIn(f'value="{op}"', html)
        # the add-student form and the row form both carry all four
        self.assertGreaterEqual(html.count('name="operations"'), 8)
        self.assertIn('set_operations', html)

    def test_manage_page_mastered_count_is_out_of_the_assigned_facts(self):
        student = make_student('kid', ['mul'])
        response = self.client.get(reverse('manage'))
        row = next(r for r in response.context['rows']
                   if r['student'].pk == student.pk)
        self.assertEqual(row['total'],
                         Fact.objects.filter(operation='mul').count())


class ReportOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seeded()

    def setUp(self):
        self.student = make_student('kid')
        self.client.login(username='kid', password='pw')

    def test_report_shows_only_the_assigned_operations(self):
        self.student.operations = ['mul']
        self.student.save()
        response = self.client.get(reverse('progress'))
        self.assertEqual(response.status_code, 200)
        ops = [g['op'] for g in response.context['grids']]
        self.assertEqual(ops, ['mul'])
        self.assertContains(response, 'Multiplication (×)')
        self.assertNotContains(response, 'Addition (+)')

    def test_report_shows_all_four_grids_when_all_are_on(self):
        self.student.operations = ['add', 'sub', 'mul', 'div']
        self.student.save()
        response = self.client.get(reverse('progress'))
        self.assertEqual([g['op'] for g in response.context['grids']],
                         ['add', 'sub', 'mul', 'div'])
        for title in ('Addition (+)', 'Subtraction (−)',
                      'Multiplication (×)', 'Division (÷)'):
            self.assertContains(response, title)

    def test_multiplication_grid_is_the_times_table(self):
        self.student.operations = ['mul']
        self.student.save()
        grid = self.client.get(reverse('progress')).context['grids'][0]
        self.assertEqual(grid['cols'], list(range(11)))
        self.assertEqual([r['head'] for r in grid['rows']], list(range(11)))
        # row 7, column 8 holds 7 x 8 and shows its answer
        cell = grid['rows'][7]['cells'][8]
        self.assertEqual(cell['label'], 56)
        self.assertIn('7 × 8 = 56', cell['title'])

    def test_division_grid_is_divisor_by_answer_showing_the_dividend(self):
        # a dividend axis would need 101 rows, so division is laid out as the
        # times table read backwards
        self.student.operations = ['div']
        self.student.save()
        grid = self.client.get(reverse('progress')).context['grids'][0]
        self.assertEqual([r['head'] for r in grid['rows']], list(range(1, 11)))
        row7 = next(r for r in grid['rows'] if r['head'] == 7)
        cell = row7['cells'][8]           # divisor 7, answer 8
        self.assertEqual(cell['label'], 56)
        self.assertIn('56 ÷ 7 = 8', cell['title'])
        self.assertTrue(grid['note'])     # the layout is explained on the page

    def test_totals_and_batches_cover_only_the_assigned_operations(self):
        self.student.operations = ['mul']
        self.student.save()
        ctx = self.client.get(reverse('progress')).context
        self.assertEqual(ctx['total_facts'],
                         Fact.objects.filter(operation='mul').count())
        labels = [b['label'] for b in ctx['batches']]
        self.assertTrue(all('Multiplication' in label for label in labels), labels)

    def test_home_counts_only_the_assigned_operations(self):
        self.student.operations = ['mul']
        self.student.save()
        ctx = self.client.get(reverse('home')).context
        self.assertEqual(ctx['total_facts'],
                         Fact.objects.filter(operation='mul').count())
        self.assertEqual(ctx['operations'], ['Multiplication'])

    def test_staff_report_uses_the_target_students_operations(self):
        self.student.operations = ['div']
        self.student.save()
        User.objects.create_user('teacher', password='pw', is_staff=True)
        self.client.login(username='teacher', password='pw')
        response = self.client.get(reverse('report', args=['kid']))
        self.assertEqual([g['op'] for g in response.context['grids']], ['div'])

    def test_selection_cannot_smuggle_in_an_unassigned_operation(self):
        self.student.operations = ['add']
        self.student.save()
        mul_ids = list(Fact.objects.filter(operation='mul')
                       .values_list('id', flat=True)[:3])
        add_id = Fact.objects.filter(operation='add').first().id
        self.client.post(reverse('select_facts'),
                         {'fact_ids': mul_ids + [add_id]})
        self.student.refresh_from_db()
        self.assertEqual(self.student.custom_selection, [add_id])


class PracticeApiOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seeded()

    def setUp(self):
        self.student = make_student('kid')
        self.client.login(username='kid', password='pw')

    def next_q(self):
        response = self.client.get(reverse('api_next'))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_answer_max_is_sent_and_matches_the_operation(self):
        for ops, expected in ((['add'], 20), (['sub'], 20),
                              (['mul'], 100), (['div'], 10)):
            self.student.operations = ops
            self.student.save()
            q = self.next_q()
            self.assertEqual(q['op'], ops[0])
            self.assertEqual(q['answer_max'], expected, ops)
            self.assertEqual(q['answer_max'], answer_max(ops[0]))

    def test_keypad_is_digits_for_times_and_divide_direct_for_plus_minus(self):
        # x and / share the 0-9 digit pad; + and - keep a button per number
        for ops, expected in ((['add'], 'direct'), (['sub'], 'direct'),
                              (['mul'], 'digits'), (['div'], 'digits')):
            self.student.operations = ops
            self.student.save()
            q = self.next_q()
            self.assertEqual(q['keypad'], expected, ops)
            self.assertEqual(q['keypad'], keypad_for(ops[0]))

    def test_answer_digits_is_sent_so_a_complete_answer_submits_itself(self):
        # regression: 5 x 1 = 5 sat there waiting for a second digit, because
        # 50-59 are all valid answers under a max of 100
        self.student.operations = ['mul']
        self.student.save()
        for _ in range(6):
            q = self.next_q()
            fact = Fact.objects.get(id=q['fact_id'])
            self.assertEqual(q['answer_digits'], len(str(fact.answer)),
                             f'{fact}')
            self.client.post(
                reverse('api_answer'),
                json.dumps({'fact_id': q['fact_id'], 'answer': fact.answer}),
                content_type='application/json')

    def test_answer_digits_present_for_every_operation(self):
        for op in ('add', 'sub', 'mul', 'div'):
            self.student.operations = [op]
            self.student.save()
            q = self.next_q()
            fact = Fact.objects.get(id=q['fact_id'])
            self.assertEqual(q['answer_digits'], len(str(fact.answer)), op)
            self.assertGreaterEqual(q['answer_digits'], 1, op)

    def test_multiplication_question_carries_a_multiplicative_model(self):
        self.student.operations = ['mul']
        self.student.save()
        q = self.next_q()
        self.assertEqual(q['symbol'], '×')
        self.assertIn(q['model'], ('groups', 'array', 'skip_line'))

    def test_division_question_carries_a_multiplicative_model(self):
        self.student.operations = ['div']
        self.student.save()
        q = self.next_q()
        self.assertEqual(q['symbol'], '÷')
        self.assertIn(q['model'], ('groups', 'array', 'skip_line'))

    def test_full_round_trip_on_a_multiplication_fact(self):
        self.student.operations = ['mul']
        self.student.save()
        q = self.next_q()
        fact = Fact.objects.get(id=q['fact_id'])
        self.assertEqual(fact.answer, fact.a * fact.b)
        data = self.client.post(
            reverse('api_answer'),
            json.dumps({'fact_id': q['fact_id'], 'answer': fact.answer}),
            content_type='application/json').json()
        self.assertTrue(data['correct'])
        self.assertEqual(data['points_earned'], srs.POINTS_FLUENT)

    def test_full_round_trip_on_a_division_fact(self):
        self.student.operations = ['div']
        self.student.save()
        q = self.next_q()
        fact = Fact.objects.get(id=q['fact_id'])
        self.assertEqual(fact.answer * fact.b, fact.a)
        data = self.client.post(
            reverse('api_answer'),
            json.dumps({'fact_id': q['fact_id'], 'answer': fact.answer}),
            content_type='application/json').json()
        self.assertTrue(data['correct'])

    def test_no_facts_returns_an_empty_marker_not_a_500(self):
        # the client stops asking on this instead of spinning on an error
        Fact.objects.all().delete()
        response = self.client.get(reverse('api_next'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['empty'])
        self.assertTrue(data['message'])

    def test_practice_page_loads_every_model_renderer(self):
        response = self.client.get(reverse('practice'))
        html = response.content.decode()
        for script in ('tenframe.js', 'numberline.js', 'rekenrek.js', 'bars.js',
                       'groups.js', 'array.js', 'skipline.js'):
            self.assertIn(script, html)

    def test_every_model_in_use_has_a_renderer_file_and_a_script_tag(self):
        # the footgun this catches: add a strategy, map it to a new picture,
        # forget to ship or load the .js — the student just sees no model
        from django.conf import settings
        from drill.strategies import STRATEGY_MODEL
        html = self.client.get(reverse('practice')).content.decode()
        js_dir = settings.BASE_DIR / 'static' / 'drill' / 'js' / 'models'
        on_disk = {p.stem: p.name for p in js_dir.glob('*.js')}
        for model in sorted(set(STRATEGY_MODEL.values())):
            stem = model.replace('_', '')
            self.assertIn(stem, on_disk, f'no renderer file for "{model}"')
            self.assertIn(on_disk[stem], html,
                          f'{on_disk[stem]} is not loaded by practice.html')


class CreateStudentCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seeded()

    def test_defaults_to_add_and_sub(self):
        call_command('create_student', 'kid', 'pw', verbosity=0)
        student = Student.objects.get(user__username='kid')
        self.assertEqual(student.operations, ['add', 'sub'])

    def test_operations_flag(self):
        call_command('create_student', 'kid', 'pw',
                     '--operations', 'mul', 'div', verbosity=0)
        student = Student.objects.get(user__username='kid')
        self.assertEqual(student.operations, ['mul', 'div'])

    def test_operations_flag_normalises_order(self):
        call_command('create_student', 'kid', 'pw',
                     '--ops', 'div', 'add', verbosity=0)
        student = Student.objects.get(user__username='kid')
        self.assertEqual(student.operations, ['add', 'div'])
