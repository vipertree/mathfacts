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
                    'strategy', 'daily'):
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

    def test_server_side_timing_used_for_points(self):
        # the client can't claim fluency: timing comes from the server clock,
        # so an instant test-client answer is "fluent" regardless of payload
        q = self.get_next()
        fact = Fact.objects.get(id=q['fact_id'])
        data = self.post_answer(q['fact_id'], fact.answer).json()
        self.assertEqual(data['points_earned'], srs.POINTS_FLUENT)
