import json

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from drill import srs
from drill.models import Attempt, DailyProgress, Fact, FactProgress, Student


class AuthWallTests(TestCase):
    def test_pages_require_login(self):
        for name in ('home', 'practice', 'progress', 'api_next'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn('/login/', response['Location'])

    def test_report_requires_staff(self):
        User.objects.create_user('kid', password='pw')
        self.client.login(username='kid', password='pw')
        response = self.client.get(reverse('report', args=['kid']))
        self.assertEqual(response.status_code, 302)  # bounced to admin login


class PracticeFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def setUp(self):
        call_command('create_student', 'kid', 'pw', '--theme', 'hightech',
                     verbosity=0)
        self.student = Student.objects.get(user__username='kid')
        self.client.login(username='kid', password='pw')

    def get_next(self):
        response = self.client.get(reverse('api_next'))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def post_answer(self, fact_id, answer):
        return self.client.post(
            reverse('api_answer'),
            json.dumps({'fact_id': fact_id, 'answer': answer}),
            content_type='application/json')

    def test_full_round_trip_correct(self):
        q = self.get_next()
        for key in ('fact_id', 'op', 'symbol', 'a', 'b', 'scaffold', 'model',
                    'strategy', 'pace_ms', 'daily'):
            self.assertIn(key, q)
        fact = Fact.objects.get(id=q['fact_id'])
        response = self.post_answer(q['fact_id'], fact.answer)
        data = response.json()
        self.assertTrue(data['correct'])
        self.assertGreater(data['points_earned'], 0)
        self.assertEqual(data['daily']['points'], data['points_earned'])
        self.assertEqual(Attempt.objects.count(), 1)
        self.assertTrue(Attempt.objects.get().correct)

    def test_wrong_answer_recorded_and_zero_points(self):
        q = self.get_next()
        fact = Fact.objects.get(id=q['fact_id'])
        data = self.post_answer(q['fact_id'], fact.answer + 1).json()
        self.assertFalse(data['correct'])
        self.assertEqual(data['answer'], fact.answer)
        self.assertEqual(data['points_earned'], 0)
        prog = FactProgress.objects.get(student=self.student, fact=fact)
        self.assertEqual(prog.lapses, 1)

    def test_answer_must_match_served_question(self):
        q = self.get_next()
        other = Fact.objects.exclude(id=q['fact_id']).first()
        response = self.post_answer(other.id, other.answer)
        self.assertEqual(response.status_code, 400)

    def test_answer_cannot_be_replayed(self):
        q = self.get_next()
        fact = Fact.objects.get(id=q['fact_id'])
        self.assertEqual(self.post_answer(q['fact_id'], fact.answer).status_code, 200)
        # second submission without a new question: rejected (no farming)
        self.assertEqual(self.post_answer(q['fact_id'], fact.answer).status_code, 400)

    def test_goal_met_flag_fires_once(self):
        self.student.daily_goal_points = 5
        self.student.save()
        met_flags = []
        for _ in range(4):
            q = self.get_next()
            fact = Fact.objects.get(id=q['fact_id'])
            met_flags.append(self.post_answer(q['fact_id'], fact.answer)
                             .json()['goal_just_met'])
        self.assertEqual(met_flags.count(True), 1)
        daily = DailyProgress.objects.get(student=self.student)
        self.assertTrue(daily.goal_met)
        self.assertEqual(daily.questions, 4)

    def test_questions_alternate_facts(self):
        q1 = self.get_next()
        fact1 = Fact.objects.get(id=q1['fact_id'])
        self.post_answer(q1['fact_id'], fact1.answer)
        q2 = self.get_next()
        self.assertNotEqual(q2['fact_id'], q1['fact_id'])

    def test_progress_page_renders(self):
        response = self.client.get(reverse('progress'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Addition')
        self.assertContains(response, 'Subtraction')

    def test_staff_report_page(self):
        User.objects.create_user('teacher', password='pw', is_staff=True)
        self.client.login(username='teacher', password='pw')
        response = self.client.get(reverse('report', args=['kid']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'kid')

    def test_theme_switch(self):
        response = self.client.post(reverse('set_theme'), {'theme': 'princess'})
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.theme, 'princess')
        # invalid themes are ignored
        self.client.post(reverse('set_theme'), {'theme': 'dinosaur'})
        self.student.refresh_from_db()
        self.assertEqual(self.student.theme, 'princess')

    def test_home_page_renders_with_theme(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hightech.css')

    def test_instructions_show_once_on_first_login(self):
        # first visit: modal auto-shows and the flag is set
        self.assertFalse(self.student.seen_instructions)
        r1 = self.client.get(reverse('home'))
        self.assertTrue(r1.context['show_instructions'])
        self.assertContains(r1, 'energy cells')  # hightech-flavored intro
        self.student.refresh_from_db()
        self.assertTrue(self.student.seen_instructions)
        # second visit: no auto-show, but the how-to button is still there
        r2 = self.client.get(reverse('home'))
        self.assertFalse(r2.context['show_instructions'])
        self.assertContains(r2, 'How to play')

    def test_instructions_text_varies_by_theme(self):
        self.client.post(reverse('set_theme'), {'theme': 'princess'})
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'jewels')
        self.assertNotContains(response, 'energy cells')

    def test_practice_page_embeds_valid_theme_json(self):
        # regression: theme data must be a JSON *object*, not a double-encoded
        # string (which made THEME.cheers undefined and broke answering).
        response = self.client.get(reverse('practice'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        start = html.index('id="theme-data"')
        blob = html[html.index('>', start) + 1:html.index('</script>', start)]
        data = json.loads(blob)
        self.assertIsInstance(data, dict)
        self.assertIsInstance(data['cheers'], list)
        self.assertTrue(data['point_icon'])
        # csrf cookie is guaranteed for the JS POSTs
        self.assertIn('csrftoken', response.cookies)

    def test_pace_window_matches_fluency_threshold(self):
        q = self.get_next()
        self.assertEqual(q['pace_ms'], srs.FLUENT_MS[q['scaffold']])
        # a brand-new fact (full scaffold) is forgiving, not a 5s sprint
        self.assertGreaterEqual(q['pace_ms'], 15000)

    def test_server_side_timing_used_for_points(self):
        # the client can't claim fluency: timing comes from the server clock,
        # so an instant test-client answer is "fluent" regardless of payload
        q = self.get_next()
        fact = Fact.objects.get(id=q['fact_id'])
        data = self.post_answer(q['fact_id'], fact.answer).json()
        self.assertEqual(data['points_earned'], srs.POINTS_FLUENT)


class ManageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def setUp(self):
        User.objects.create_user('teacher', password='pw', is_staff=True)
        self.client.login(username='teacher', password='pw')

    def test_manage_requires_staff(self):
        self.client.logout()
        User.objects.create_user('kid', password='pw')
        self.client.login(username='kid', password='pw')
        self.assertEqual(self.client.get(reverse('manage')).status_code, 302)

    def test_add_student_creates_user_and_student(self):
        response = self.client.post(reverse('manage'), {
            'action': 'add_student', 'username': 'newkid',
            'password': 'pw12', 'theme': 'princess', 'goal': 200})
        self.assertRedirects(response, reverse('manage'))
        student = Student.objects.get(user__username='newkid')
        self.assertEqual(student.theme, 'princess')
        self.assertEqual(student.daily_goal_points, 200)
        self.assertTrue(student.user.check_password('pw12'))

    def test_add_duplicate_username_rejected(self):
        User.objects.create_user('dupe', password='x')
        self.client.post(reverse('manage'), {
            'action': 'add_student', 'username': 'dupe', 'password': 'pw12'})
        self.assertEqual(User.objects.filter(username='dupe').count(), 1)

    def test_reset_password(self):
        u = User.objects.create_user('kid', password='old1')
        s = Student.objects.create(user=u)
        self.client.post(reverse('manage'), {
            'action': 'reset_password', 'student_id': s.pk, 'password': 'new1'})
        u.refresh_from_db()
        self.assertTrue(u.check_password('new1'))


class ReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def setUp(self):
        call_command('create_student', 'kid', 'pw', verbosity=0)
        self.student = Student.objects.get(user__username='kid')
        self.client.login(username='kid', password='pw')

    def test_progress_shows_four_levels_and_selection(self):
        r = self.client.get(reverse('progress'))
        self.assertEqual(r.status_code, 200)
        for label in ('Mastered', 'Proficient', 'Needs practice', 'Not tested yet'):
            self.assertContains(r, label)
        self.assertTrue(r.context['can_select'])
        self.assertContains(r, 'select-form')          # selection toolbar present
        self.assertContains(r, 'data-fact-id')          # cells are selectable

    def test_cells_show_answers(self):
        r = self.client.get(reverse('progress'))
        # 9 + 4 = 13 cell should carry its answer and a status title
        self.assertContains(r, 'data-fact-id')
        self.assertContains(r, 'Not tested yet')

    def test_staff_report_has_no_selection_toolbar(self):
        User.objects.create_user('teacher', password='pw', is_staff=True)
        self.client.login(username='teacher', password='pw')
        r = self.client.get(reverse('report', args=['kid']))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context['can_select'])
        self.assertNotContains(r, 'select-form')


class CustomPracticeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_facts', verbosity=0)

    def setUp(self):
        call_command('create_student', 'kid', 'pw', verbosity=0)
        self.student = Student.objects.get(user__username='kid')
        self.client.login(username='kid', password='pw')
        self.picks = list(Fact.objects.all()[:3].values_list('id', flat=True))

    def test_select_saves_and_launches(self):
        r = self.client.post(reverse('select_facts'), {'fact_ids': self.picks})
        self.assertRedirects(r, reverse('practice_custom'))
        self.student.refresh_from_db()
        self.assertEqual(sorted(self.student.custom_selection), sorted(self.picks))

    def test_select_ignores_bogus_ids(self):
        self.client.post(reverse('select_facts'),
                         {'fact_ids': self.picks + [999999]})
        self.student.refresh_from_db()
        self.assertEqual(sorted(self.student.custom_selection), sorted(self.picks))

    def test_custom_practice_requires_a_selection(self):
        r = self.client.get(reverse('practice_custom'))
        self.assertRedirects(r, reverse('progress'))

    def test_custom_only_serves_selected_and_skips_daily(self):
        self.client.post(reverse('select_facts'), {'fact_ids': self.picks})
        self.client.get(reverse('practice_custom'))  # sets custom mode
        # several questions all come from the selected set
        for _ in range(5):
            q = self.client.get(reverse('api_next')).json()
            self.assertIn(q['fact_id'], self.picks)
            self.assertTrue(q['custom'])
            fact = Fact.objects.get(id=q['fact_id'])
            data = self.client.post(
                reverse('api_answer'),
                json.dumps({'fact_id': q['fact_id'], 'answer': fact.answer}),
                content_type='application/json').json()
            self.assertTrue(data['correct'])
            self.assertEqual(data['points_earned'], 0)   # not counted
            self.assertTrue(data['custom'])
        # daily goal untouched...
        self.assertEqual(DailyProgress.objects.filter(student=self.student).count(), 0)
        # ...but the facts' progress did improve (practice still teaches)
        self.assertTrue(FactProgress.objects.filter(
            student=self.student, fact_id__in=self.picks, box__gte=1).exists())

    def test_switching_back_to_srs_counts_again(self):
        self.client.post(reverse('select_facts'), {'fact_ids': self.picks})
        self.client.get(reverse('practice_custom'))
        self.client.get(reverse('practice'))  # back to normal mode
        q = self.client.get(reverse('api_next')).json()
        self.assertFalse(q['custom'])
        fact = Fact.objects.get(id=q['fact_id'])
        data = self.client.post(
            reverse('api_answer'),
            json.dumps({'fact_id': q['fact_id'], 'answer': fact.answer}),
            content_type='application/json').json()
        self.assertGreater(data['points_earned'], 0)
        self.assertEqual(DailyProgress.objects.filter(student=self.student).count(), 1)
