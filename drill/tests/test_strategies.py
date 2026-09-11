from django.test import SimpleTestCase

from itertools import groupby

from drill.strategies import (ANSWER_MAX, KEYPAD, MUL_MAX, OPERATIONS,
                              STAGE_LABELS, STAGES_BY_OP, STRATEGY_MODEL,
                              answer_max, generate_facts, grid_cell, grid_spec,
                              keypad_for, stage_for, strategy_for,
                              teaching_sequence)


class GenerateFactsTests(SimpleTestCase):
    def setUp(self):
        self.facts = list(generate_facts())

    def test_full_domain_counts(self):
        counts = {op: 0 for op in ('add', 'sub', 'mul', 'div')}
        for f in self.facts:
            counts[f[0]] += 1
        self.assertEqual(counts['add'], 231)   # a,b >= 0, a+b <= 20
        self.assertEqual(counts['sub'], 231)   # 0 <= b <= a <= 20
        self.assertEqual(counts['mul'], 121)   # 0..10 x 0..10
        self.assertEqual(counts['div'], 110)   # divisor 1..10, quotient 0..10

    def test_answers_in_range(self):
        expect = {
            'add': lambda a, b: a + b,
            'sub': lambda a, b: a - b,
            'mul': lambda a, b: a * b,
            'div': lambda a, b: a // b,
        }
        for op, a, b, answer, _strategy, _stage, _order in self.facts:
            self.assertEqual(answer, expect[op](a, b), f'{op} {a} {b}')
            self.assertTrue(0 <= answer <= answer_max(op), f'{op} {a} {b}')

    def test_no_division_by_zero_is_generated(self):
        self.assertFalse([f for f in self.facts if f[0] == 'div' and f[2] == 0])

    def test_division_facts_are_exact(self):
        for op, a, b, answer, _s, _stg, _o in self.facts:
            if op == 'div':
                self.assertEqual(a % b, 0, f'{a}/{b} is not a whole fact')
                self.assertEqual(answer * b, a)

    def test_factors_stay_inside_the_tables(self):
        for op, a, b, answer, _s, _stg, _o in self.facts:
            if op == 'mul':
                self.assertLessEqual(max(a, b), MUL_MAX, f'{a}x{b}')
            elif op == 'div':
                self.assertLessEqual(b, MUL_MAX, f'{a}/{b}')
                self.assertLessEqual(answer, MUL_MAX, f'{a}/{b}')

    def test_answer_max_matches_the_real_domain(self):
        # the keypad range the client is told about must actually cover every
        # answer that operation can ask for
        widest = {}
        for op, _a, _b, answer, _s, _stg, _o in self.facts:
            widest[op] = max(widest.get(op, 0), answer)
        for op, most in widest.items():
            self.assertLessEqual(most, ANSWER_MAX[op], op)
        self.assertEqual(widest['mul'], ANSWER_MAX['mul'])   # 10x10 = 100
        self.assertEqual(widest['div'], ANSWER_MAX['div'])   # 100/10 = 10

    def test_every_fact_has_known_strategy_and_stage(self):
        for op, a, b, _ans, strategy, stage, _order in self.facts:
            self.assertIn(strategy, STRATEGY_MODEL, f'{op} {a} {b}')
            self.assertIn(stage, STAGE_LABELS, f'{op} {a} {b}')

    def test_intro_order_is_a_dense_permutation(self):
        orders = sorted(f[6] for f in self.facts)
        self.assertEqual(orders, list(range(len(self.facts))))

    def test_all_stages_populated(self):
        used = {f[5] for f in self.facts}
        self.assertEqual(used, set(STAGE_LABELS))  # 1..20 all present

    def test_stages_by_op_matches_stage_for(self):
        # STAGES_BY_OP is what the report filters batches with; it must agree
        # with the batches stage_for actually hands out
        actual = {}
        for op, _a, _b, _ans, _s, stage, _o in self.facts:
            actual.setdefault(op, set()).add(stage)
        for op, stages in STAGES_BY_OP.items():
            self.assertEqual(actual[op], set(stages), op)

    def test_every_fact_lands_in_a_unique_grid_cell(self):
        placed = {}
        for op, a, b, answer, _s, _stg, _o in self.facts:
            spec = grid_spec(op)
            row, col = grid_cell(op, a, b, answer)
            self.assertIn(row, spec['rows'], f'{op} {a} {b} row {row}')
            self.assertIn(col, spec['cols'], f'{op} {a} {b} col {col}')
            key = (op, row, col)
            self.assertNotIn(key, placed,
                             f'{op} {a} {b} collides with {placed.get(key)}')
            placed[key] = (a, b)


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
        # multiplication: families keyed on the smaller factor
        ('mul', 4, 0, 'mul_zero'),
        ('mul', 0, 7, 'mul_zero'),
        ('mul', 1, 7, 'mul_one'),
        ('mul', 7, 1, 'mul_one'),
        ('mul', 2, 9, 'mul_double'),
        ('mul', 9, 2, 'mul_double'),
        ('mul', 3, 8, 'mul_groups'),
        ('mul', 4, 7, 'mul_groups'),
        ('mul', 5, 7, 'mul_skip_five'),
        ('mul', 7, 5, 'mul_skip_five'),
        ('mul', 10, 7, 'mul_skip_ten'),
        ('mul', 7, 10, 'mul_skip_ten'),
        ('mul', 7, 7, 'mul_square'),
        ('mul', 6, 6, 'mul_square'),
        ('mul', 9, 6, 'mul_nine'),
        ('mul', 6, 9, 'mul_nine'),
        ('mul', 9, 9, 'mul_square'),   # a square wins over the nines trick
        ('mul', 7, 8, 'mul_break_apart'),
        ('mul', 8, 6, 'mul_break_apart'),
        # division
        ('div', 0, 5, 'div_zero'),
        ('div', 7, 1, 'div_by_one'),
        ('div', 70, 10, 'div_by_ten'),
        ('div', 8, 8, 'div_self'),
        ('div', 14, 2, 'div_halve'),
        ('div', 35, 5, 'div_by_five'),
        ('div', 18, 3, 'div_share'),
        ('div', 28, 4, 'div_share'),
        ('div', 49, 7, 'div_square'),
        ('div', 36, 6, 'div_square'),
        ('div', 56, 7, 'div_think_mul'),
        ('div', 48, 6, 'div_think_mul'),
    ]

    def test_strategy_spot_checks(self):
        for op, a, b, expected in self.CASES:
            self.assertEqual(strategy_for(op, a, b), expected, f'{op} {a} {b}')

    def test_unknown_operation_raises(self):
        with self.assertRaises(ValueError):
            strategy_for('pow', 2, 3)
        with self.assertRaises(ValueError):
            stage_for('pow', 2, 3)

    def test_dividing_by_zero_raises(self):
        with self.assertRaises(ValueError):
            strategy_for('div', 6, 0)
        with self.assertRaises(ValueError):
            stage_for('div', 6, 0)


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
        # multiplication: 9 free families, 10 twos, 11 fives, 12 threes/fours,
        # 13 squares, 14 the tricky 6-9 facts
        ('mul', 0, 4, 9), ('mul', 1, 8, 9), ('mul', 10, 10, 9), ('mul', 7, 10, 9),
        ('mul', 2, 8, 10), ('mul', 9, 2, 10),
        ('mul', 5, 9, 11), ('mul', 5, 5, 11),
        ('mul', 3, 7, 12), ('mul', 4, 4, 12), ('mul', 8, 3, 12),
        ('mul', 6, 6, 13), ('mul', 7, 7, 13), ('mul', 9, 9, 13),
        ('mul', 7, 8, 14), ('mul', 9, 6, 14), ('mul', 6, 7, 14),
        # division mirrors it
        ('div', 0, 7, 15), ('div', 9, 1, 15), ('div', 60, 10, 15), ('div', 6, 6, 15),
        ('div', 16, 2, 16),
        ('div', 45, 5, 17),
        ('div', 21, 3, 18), ('div', 32, 4, 18),
        ('div', 36, 6, 19), ('div', 64, 8, 19),
        ('div', 56, 7, 20), ('div', 54, 6, 20),
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

    def test_the_sequence_opens_inside_the_first_batch(self):
        # which fact comes first is now down to the scatter (and the SRS picks
        # randomly from a window on top of that), but it must be a batch-1 fact
        first = min(self.order.values())
        op, a, b = next(k for k, v in self.order.items() if v == first)
        self.assertEqual(stage_for(op, a, b), 1)


class FourOperationOrderTests(SimpleTestCase):
    """Where multiplication and division sit in the global teaching order."""

    def setUp(self):
        self.facts = list(generate_facts())
        self.order = {(op, a, b): o
                      for op, a, b, _ans, _s, _stg, o in self.facts}

    def positions(self, *ops):
        return [o for (op, _a, _b), o in self.order.items() if op in ops]

    def test_add_sub_all_come_before_mul_div(self):
        self.assertLess(max(self.positions('add', 'sub')),
                        min(self.positions('mul', 'div')))

    def test_multiplication_comes_before_division(self):
        self.assertLess(max(self.positions('mul')), min(self.positions('div')))

    def test_intro_order_is_still_a_dense_permutation(self):
        self.assertEqual(sorted(self.order.values()),
                         list(range(len(self.order))))

    def test_easy_multiplication_families_come_first(self):
        # x1 and x10 before the twos, twos before the fives, and the tricky
        # 6-9 facts dead last
        self.assertLess(self.order[('mul', 1, 8)], self.order[('mul', 2, 8)])
        self.assertLess(self.order[('mul', 2, 8)], self.order[('mul', 5, 8)])
        self.assertLess(self.order[('mul', 5, 8)], self.order[('mul', 7, 8)])
        self.assertEqual(max(self.positions('mul')),
                         max(o for (op, a, b), o in self.order.items()
                             if op == 'mul' and min(a, b) >= 6 and a != b))

    def test_multiplication_grows_by_the_larger_factor(self):
        # every fact whose biggest factor is <= 4 comes before any fact with a
        # factor of 8, regardless of which batch they landed in
        small = [o for (op, a, b), o in self.order.items()
                 if op == 'mul' and max(a, b) <= 4]
        big = [o for (op, a, b), o in self.order.items()
               if op == 'mul' and max(a, b) == 8 and min(a, b) >= 6]
        self.assertLess(max(small), min(big))


class ModelChoiceTests(SimpleTestCase):
    """Each new strategy has to point at the picture that actually shows it."""

    def test_multiplication_uses_the_multiplicative_models(self):
        expected = {
            'mul_zero': 'groups', 'mul_one': 'groups', 'mul_double': 'groups',
            'mul_groups': 'groups',
            'mul_skip_five': 'skip_line', 'mul_skip_ten': 'skip_line',
            'mul_square': 'array', 'mul_nine': 'array',
            'mul_break_apart': 'array',
        }
        for strategy, model in expected.items():
            self.assertEqual(STRATEGY_MODEL[strategy], model, strategy)

    def test_division_uses_the_multiplicative_models(self):
        expected = {
            'div_zero': 'groups', 'div_by_one': 'groups', 'div_self': 'groups',
            'div_halve': 'groups', 'div_share': 'groups',
            'div_by_five': 'skip_line', 'div_by_ten': 'skip_line',
            'div_square': 'array', 'div_think_mul': 'array',
        }
        for strategy, model in expected.items():
            self.assertEqual(STRATEGY_MODEL[strategy], model, strategy)

    def test_no_multiplicative_fact_uses_an_additive_model(self):
        additive = {'ten_frame', 'number_line', 'rekenrek', 'bars'}
        for op, a, b, _ans, strategy, _stg, _o in generate_facts():
            if op in ('mul', 'div'):
                self.assertNotIn(STRATEGY_MODEL[strategy], additive,
                                 f'{op} {a} {b} ({strategy})')

    def test_no_additive_fact_uses_a_multiplicative_model(self):
        multiplicative = {'groups', 'array', 'skip_line'}
        for op, a, b, _ans, strategy, _stg, _o in generate_facts():
            if op in ('add', 'sub'):
                self.assertNotIn(STRATEGY_MODEL[strategy], multiplicative,
                                 f'{op} {a} {b} ({strategy})')


class KeypadTests(SimpleTestCase):
    """Which keypad each operation asks for."""

    def test_every_operation_names_a_keypad(self):
        self.assertEqual(set(KEYPAD), set(OPERATIONS))
        for op in OPERATIONS:
            self.assertIn(keypad_for(op), ('direct', 'digits'), op)

    def test_multiplicative_operations_use_the_digit_pad(self):
        # a 0-9 pad for both, so x and / type the same way even though
        # division's 0-10 answers would fit on a direct pad
        self.assertEqual(keypad_for('mul'), 'digits')
        self.assertEqual(keypad_for('div'), 'digits')

    def test_additive_operations_keep_a_button_per_number(self):
        self.assertEqual(keypad_for('add'), 'direct')
        self.assertEqual(keypad_for('sub'), 'direct')

    def test_direct_pads_stay_small_enough_to_tap(self):
        # a direct pad draws answer_max + 1 buttons; past ~21 that is a wall
        for op in OPERATIONS:
            if keypad_for(op) == 'direct':
                self.assertLessEqual(answer_max(op), 20, op)


class AnswerVarietyTests(SimpleTestCase):
    """The sequence a student actually experiences has to feel varied.

    What went wrong before: addition's within-batch sort key was `a + b`, which
    *is* the answer — so the batch came out as every fact answering 11, then
    every fact answering 12, in runs of eight. The first fix (always take the
    largest remaining answer-group) removed the runs but produced a sawtooth,
    "11 12 11 13 12 11 14 13 12 11 …", which is just as monotonous to drill.
    These tests pin the property rather than either mechanism.
    """

    WINDOW = 8   # roughly what a student meets in a short sitting

    def setUp(self):
        self.facts = list(generate_facts())
        self.answers = [f[3] for f in self.facts]
        self.batches = {}
        for op, a, b, answer, _s, stage, order in self.facts:
            self.batches.setdefault(stage, []).append((order, op, a, b, answer))
        for rows in self.batches.values():
            rows.sort()

    @staticmethod
    def _longest_run(values):
        return max(len(list(g)) for _k, g in groupby(values))

    def test_no_two_consecutive_facts_share_an_answer_within_a_batch(self):
        for stage, rows in self.batches.items():
            run = self._longest_run([r[4] for r in rows])
            self.assertEqual(run, 1,
                             f'batch {stage} repeats an answer {run} times in a row')

    def test_no_run_of_identical_answers_across_the_whole_sequence(self):
        # a batch boundary can put two equal answers next to each other, which
        # is fine; three would not be
        run = self._longest_run(self.answers)
        self.assertLessEqual(run, 2, f'{run} identical answers in a row')

    def test_every_short_sitting_sees_several_different_answers(self):
        worst, where = self.WINDOW, None
        for i in range(len(self.answers) - self.WINDOW + 1):
            distinct = len(set(self.answers[i:i + self.WINDOW]))
            if distinct < worst:
                worst, where = distinct, i
        self.assertGreaterEqual(
            worst, 3,
            f'only {worst} distinct answers in facts {where}-{where + self.WINDOW}')

    def test_answers_are_not_a_monotonic_staircase(self):
        # the sawtooth regression: a long strictly-descending (or ascending)
        # stretch of answers reads as a pattern, not as practice
        longest = best = 1
        for prev, cur in zip(self.answers, self.answers[1:]):
            best = best + 1 if cur < prev else 1
            longest = max(longest, best)
        self.assertLessEqual(longest, 7,
                             f'{longest} answers in a row descending')

    def test_zero_facts_do_not_clump(self):
        # "x + 0" / "0 x n" style facts are trivial; a run of them is dull
        trivial = [1 if (a == 0 or b == 0) else 0
                   for _op, a, b, _ans, _s, _stg, _o in self.facts]
        for i in range(len(trivial) - self.WINDOW + 1):
            self.assertLessEqual(
                sum(trivial[i:i + self.WINDOW]), 5,
                f'too many trivial facts among facts {i}-{i + self.WINDOW}')

    def test_the_sequence_is_reproducible(self):
        # seed_facts is idempotent and reruns must not renumber the sequence
        self.assertEqual(teaching_sequence(), teaching_sequence())
        self.assertEqual([f[6] for f in generate_facts()],
                         [f[6] for f in generate_facts()])

    def test_variety_does_not_break_the_batch_progression(self):
        # scattering happens strictly inside a batch: batch k is still
        # finished before batch k+1 starts
        spans = {}
        for _op, _a, _b, _ans, _s, stage, order in self.facts:
            lo, hi = spans.get(stage, (order, order))
            spans[stage] = (min(lo, order), max(hi, order))
        for earlier, later in zip(sorted(spans), sorted(spans)[1:]):
            self.assertLess(spans[earlier][1], spans[later][0],
                            f'batch {earlier} overlaps batch {later}')
