from django.test import SimpleTestCase

from drill.strategies import STAGES, STRATEGY_MODEL, classify, generate_facts


class GenerateFactsTests(SimpleTestCase):
    def setUp(self):
        self.facts = list(generate_facts())

    def test_full_domain_counts(self):
        adds = [f for f in self.facts if f[0] == 'add']
        subs = [f for f in self.facts if f[0] == 'sub']
        # additions with a,b >= 0 and a+b <= 20: triangular count = 231
        self.assertEqual(len(adds), 231)
        # subtractions with 0 <= b <= a <= 20: also 231
        self.assertEqual(len(subs), 231)

    def test_answers_in_range(self):
        for op, a, b, answer, _, _ in self.facts:
            expected = a + b if op == 'add' else a - b
            self.assertEqual(answer, expected)
            self.assertTrue(0 <= answer <= 20, f'{op} {a} {b}')

    def test_every_fact_classified_with_known_strategy_and_stage(self):
        for op, a, b, _, strategy, stage in self.facts:
            self.assertIn(strategy, STRATEGY_MODEL, f'{op} {a} {b}')
            self.assertEqual(stage, STAGES[strategy])

    def test_all_stages_populated(self):
        used = {stage for *_, stage in self.facts}
        self.assertEqual(used, set(STAGES.values()))


class ClassifySpotChecks(SimpleTestCase):
    CASES = [
        ('add', 7, 0, 'add_zero'),
        ('add', 0, 17, 'add_zero'),
        ('add', 6, 1, 'count_on_1'),
        ('add', 2, 9, 'count_on_2'),
        ('add', 7, 7, 'doubles'),
        ('add', 10, 10, 'doubles'),
        ('add', 4, 6, 'combos_of_10'),
        ('add', 10, 5, 'plus_ten'),
        ('add', 13, 4, 'teen_structure'),
        ('add', 6, 7, 'near_doubles'),
        ('add', 3, 5, 'add_within_10'),
        ('add', 9, 4, 'make_ten'),
        ('add', 8, 5, 'make_ten'),
        ('sub', 9, 0, 'sub_zero'),
        ('sub', 12, 12, 'sub_zero'),
        ('sub', 8, 1, 'count_back_1'),
        ('sub', 11, 2, 'count_back_2'),
        ('sub', 9, 8, 'count_up'),
        ('sub', 13, 11, 'count_up'),
        ('sub', 12, 6, 'halves'),
        ('sub', 10, 3, 'subtract_from_10'),
        ('sub', 17, 10, 'minus_ten'),
        ('sub', 17, 7, 'teens_minus_ones'),
        ('sub', 17, 5, 'teen_parts'),
        ('sub', 13, 5, 'back_to_ten'),
        ('sub', 14, 9, 'take_from_ten'),
        ('sub', 20, 3, 'take_from_ten'),
        ('sub', 9, 4, 'think_addition'),
    ]

    def test_spot_checks(self):
        for op, a, b, expected in self.CASES:
            strategy, stage = classify(op, a, b)
            self.assertEqual(strategy, expected, f'{op} {a} {b}')
            self.assertEqual(stage, STAGES[expected])

    def test_unknown_operation_raises(self):
        with self.assertRaises(ValueError):
            classify('mul', 2, 3)
