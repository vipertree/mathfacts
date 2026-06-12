from django.test import SimpleTestCase

from drill.strategies import (STAGE_LABELS, STRATEGY_MODEL, generate_facts,
                              stage_for, strategy_for)


class GenerateFactsTests(SimpleTestCase):
    def setUp(self):
        self.facts = list(generate_facts())

    def test_full_domain_counts(self):
        adds = [f for f in self.facts if f[0] == 'add']
        subs = [f for f in self.facts if f[0] == 'sub']
        self.assertEqual(len(adds), 231)   # a,b >= 0, a+b <= 20
        self.assertEqual(len(subs), 231)   # 0 <= b <= a <= 20

    def test_answers_in_range(self):
        for op, a, b, answer, _strategy, _stage, _order in self.facts:
            expected = a + b if op == 'add' else a - b
            self.assertEqual(answer, expected)
            self.assertTrue(0 <= answer <= 20, f'{op} {a} {b}')

    def test_every_fact_has_known_strategy_and_stage(self):
        for op, a, b, _ans, strategy, stage, _order in self.facts:
            self.assertIn(strategy, STRATEGY_MODEL, f'{op} {a} {b}')
            self.assertIn(stage, STAGE_LABELS, f'{op} {a} {b}')

    def test_intro_order_is_a_dense_permutation(self):
        orders = sorted(f[6] for f in self.facts)
        self.assertEqual(orders, list(range(len(self.facts))))

    def test_all_eight_stages_populated(self):
        used = {f[5] for f in self.facts}
        self.assertEqual(used, set(STAGE_LABELS))  # 1..8 all present


class StrategySpotChecks(SimpleTestCase):
    CASES = [
        ('add', 7, 0, 'add_zero'),
        ('add', 6, 1, 'count_on_1'),
        ('add', 2, 9, 'count_on_2'),
        ('add', 7, 7, 'doubles'),
        ('add', 4, 6, 'combos_of_10'),
        ('add', 10, 5, 'plus_ten'),
        ('add', 13, 4, 'teen_structure'),
        ('add', 6, 7, 'near_doubles'),
        ('add', 3, 5, 'add_within_10'),
        ('add', 9, 4, 'make_ten'),
        ('sub', 9, 0, 'sub_zero'),
        ('sub', 8, 1, 'count_back_1'),
        ('sub', 11, 2, 'count_back_2'),
        ('sub', 9, 8, 'count_up'),
        ('sub', 12, 6, 'halves'),
        ('sub', 10, 3, 'subtract_from_10'),
        ('sub', 17, 10, 'minus_ten'),
        ('sub', 17, 7, 'teens_minus_ones'),
        ('sub', 17, 5, 'teen_parts'),
        ('sub', 13, 5, 'back_to_ten'),
        ('sub', 14, 9, 'take_from_ten'),
        ('sub', 9, 4, 'think_addition'),
    ]

    def test_strategy_spot_checks(self):
        for op, a, b, expected in self.CASES:
            self.assertEqual(strategy_for(op, a, b), expected, f'{op} {a} {b}')

    def test_unknown_operation_raises(self):
        with self.assertRaises(ValueError):
            strategy_for('mul', 2, 3)


class StageSpotChecks(SimpleTestCase):
    CASES = [
        # addition: 1 within-5, 3 sums-to-10, 5 tens/teens, 7 bridging
        ('add', 5, 5, 1), ('add', 0, 0, 1), ('add', 5, 0, 1),
        ('add', 6, 4, 3), ('add', 7, 3, 3), ('add', 9, 1, 3), ('add', 10, 0, 3),
        ('add', 10, 5, 5), ('add', 13, 4, 5), ('add', 14, 0, 5), ('add', 11, 9, 5),
        ('add', 9, 4, 7), ('add', 8, 8, 7), ('add', 6, 6, 7), ('add', 6, 5, 7),
        # subtraction: 2 within-5, 4 within-10, 6 teen no-regroup, 8 through-ten
        ('sub', 5, 2, 2), ('sub', 4, 4, 2),
        ('sub', 10, 6, 4), ('sub', 9, 4, 4), ('sub', 10, 3, 4),
        ('sub', 17, 10, 6), ('sub', 17, 5, 6), ('sub', 17, 7, 6),
        ('sub', 19, 3, 6), ('sub', 20, 3, 6),
        ('sub', 13, 5, 8), ('sub', 14, 9, 8), ('sub', 12, 6, 8), ('sub', 11, 2, 8),
    ]

    def test_stage_spot_checks(self):
        for op, a, b, expected in self.CASES:
            self.assertEqual(stage_for(op, a, b), expected, f'{op} {a} {b}')


class TeachingOrderTests(SimpleTestCase):
    """The pedagogical guarantees the order has to keep."""

    def setUp(self):
        self.order = {(op, a, b): o
                      for op, a, b, _ans, _s, _stg, o in generate_facts()}

    def o(self, op, a, b):
        return self.order[(op, a, b)]

    def test_small_facts_before_trivial_big_ones(self):
        # the user's explicit example: 5+5 must come before 14+0
        self.assertLess(self.o('add', 5, 5), self.o('add', 14, 0))

    def test_all_within_ten_before_any_teen_result(self):
        within = [o for (op, a, b), o in self.order.items()
                  if (op == 'add' and a + b <= 10) or (op == 'sub' and a <= 10)]
        teen = [o for (op, a, b), o in self.order.items()
                if (op == 'add' and a + b >= 11) or (op == 'sub' and a >= 11)]
        self.assertLess(max(within), min(teen))

    def test_addition_grows_by_sum(self):
        # every sum-<=10 addition fact precedes every sum->=11 addition fact
        small = [o for (op, a, b), o in self.order.items()
                 if op == 'add' and a + b <= 10]
        big = [o for (op, a, b), o in self.order.items()
               if op == 'add' and a + b >= 11]
        self.assertLess(max(small), min(big))

    def test_no_monotonous_plus_zero_opening(self):
        # balanced/doubles facts come before the trivial +0 facts of the same
        # size, so the opening isn't a run of "x+0"
        self.assertLess(self.o('add', 1, 1), self.o('add', 5, 0))
        self.assertLess(self.o('add', 2, 2), self.o('add', 0, 4))

    def test_first_fact_is_zero_plus_zero(self):
        self.assertEqual(self.o('add', 0, 0), 0)
