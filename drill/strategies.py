"""
Two independent things are decided here for every fact:

1. **strategy** (``strategy_for``) — the mental strategy we want the visual
   model to evoke (make-ten, near-doubles, back-to-ten, skip-count, break the
   array apart, ...). ``STRATEGY_MODEL`` maps each strategy to the picture that
   best shows it. This drives *what the student sees*, not when they see it.

2. **teaching order** (``stage_for`` + ``generate_facts``) — *when* a fact is
   introduced. Order is driven by **magnitude first**, not by strategy: all
   facts within ten come before any teen-result fact, so a trivial ``14 + 0``
   never appears before ``5 + 5``. Batches are broad and mix strategies inside
   them, so practice stays varied instead of grinding "+0, then +1, then +2".

   The batches (``STAGE_LABELS``) — 1-8 addition/subtraction, 9-14
   multiplication, 15-20 division:
     1 add, both addends 0-5            (sums to 10, small)
     2 sub, minuend 0-5
     3 add, rest of sums to 10          (one addend 6-10, e.g. 7+3, 9+1)
     4 sub, minuend 6-10
     5 add, teen result with a 10-19 addend (place value: 13+4, 10+6, no bridge)
     6 sub, teen minuend, no regrouping (17-5, 19-3, 17-10)
     7 add, teen result, both addends <=9 (bridging ten: 9+4, 8+6, doubles)
     8 sub, teen minuend, regrouping    (13-5, 14-9, 12-6)
     9 mul, x0 / x1 / x10               (the free families)
    10 mul, x2                          (doubling)
    11 mul, x5                          (skip-count by five)
    12 mul, x3 and x4                   (count/skip equal groups)
    13 mul, squares 6x6-10x10
    14 mul, the tricky 6-9 facts        (break the array apart, x9 = x10 - 1)
    15 div, /1 /10, n/n, 0/n            (the free families)
    16 div, /2                          (halving)
    17 div, /5
    18 div, /3 and /4                   (equal sharing)
    19 div, squares (36/6 ... 100/10)
    20 div, the tricky 6-9 facts        (think multiplication)

   Multiplication and division come after addition and subtraction in the
   global order, but *which* operations a given student ever sees is a
   per-student setting (``Student.operations``) — the SRS filters the domain to
   the enabled operations, so a mul-only student starts at batch 9.

   **The batch is the bucket.** Inside one, facts are deliberately *not* put in
   any order: a batch is homogeneous by construction, so ordering it buys no
   pedagogy, and the obvious orderings actively hurt. Sorting addition by sum
   made the sum the sort key, so a student met all eight ways to answer 11,
   then all seven ways to answer 12, in runs. ``_order_batch`` shuffles the
   batch under a fixed seed and then spreads it so consecutive facts answer
   differently (see ``_spread`` for why "largest group first" isn't enough).
   The absolute sequence position is stored as ``intro_order`` and is what the
   SRS introduces in; ``srs.NEW_FACT_WINDOW`` widens it per student, and
   ``srs._next_new_fact`` additionally avoids answers already in the working
   set.
"""

import random

# Visual model ids understood by static/drill/js/models/*.js
TEN_FRAME = 'ten_frame'
NUMBER_LINE = 'number_line'
REKENREK = 'rekenrek'
BARS = 'bars'
GROUPS = 'groups'          # equal groups: count the groups, count in each
ARRAY = 'array'            # array / area model, optionally broken apart
SKIP_LINE = 'skip_line'    # number line with equal hops (skip counting)

# Largest factor drilled for x and /. Bump to 12 and reseed for 12s tables;
# every axis, grid and answer range below is derived from this.
MUL_MAX = 10

# Highest answer a student can be asked to enter, per operation. Bounds the
# keypad and the typed-answer auto-submit.
ANSWER_MAX = {
    'add': 20,
    'sub': 20,
    'mul': MUL_MAX * MUL_MAX,
    'div': MUL_MAX,
}

# Which keypad the practice screen shows. 'direct' is a button per number, so
# every answer is one tap — the right thing for + and -, where the range is
# 0-20. 'digits' is a 0-9 pad with backspace and enter: x and / both use it,
# so the two multiplicative operations feel the same to type even though
# division's answers would fit on a direct pad.
KEYPAD = {
    'add': 'direct',
    'sub': 'direct',
    'mul': 'digits',
    'div': 'digits',
}

STRATEGY_MODEL = {
    # addition
    'add_zero': TEN_FRAME,        # n+0: see the amount, nothing changes
    'count_on_1': NUMBER_LINE,    # n+1: one hop
    'count_on_2': NUMBER_LINE,    # n+2: two hops
    'doubles': REKENREK,          # n+n: matching rows of beads
    'combos_of_10': TEN_FRAME,    # a+b=10: fill the frame
    'plus_ten': BARS,             # 10+n: place-value bar (10 and n)
    'teen_structure': BARS,       # teen+n, no bridge: 13+4 = 10+3+4
    'near_doubles': REKENREK,     # 6+7 = 6+6+1: the one extra bead
    'add_within_10': BARS,        # leftover small facts: part-part-whole
    'make_ten': TEN_FRAME,        # 9+4: move 1 to fill the frame, 10+3
    # subtraction
    'sub_zero': TEN_FRAME,        # n-0 / n-n
    'count_back_1': NUMBER_LINE,  # n-1: one hop back
    'count_back_2': NUMBER_LINE,  # n-2: two hops back
    'count_up': NUMBER_LINE,      # 9-8: gap of 1 or 2, count up
    'halves': REKENREK,           # 12-6: think doubles
    'subtract_from_10': TEN_FRAME,  # 10-b: empty part of the frame
    'minus_ten': BARS,            # 17-10: place value
    'teens_minus_ones': BARS,     # 17-7: strip the ones digit
    'teen_parts': BARS,           # 17-5: subtract within the ones
    'think_addition': BARS,       # 9-4: what plus 4 makes 9?
    'back_to_ten': NUMBER_LINE,   # 13-5: hop back 3 to 10, then 2 more
    'take_from_ten': TEN_FRAME,   # 14-9: take 9 from the full frame, add 4 back
    # multiplication
    'mul_zero': GROUPS,           # 4x0 / 0x4: four empty plates is still none
    'mul_one': GROUPS,            # 1x7 / 7x1: one group, or groups of one
    'mul_double': GROUPS,         # 2xn: two equal groups = double it
    'mul_groups': GROUPS,         # 3xn, 4xn: count the groups
    'mul_skip_five': SKIP_LINE,   # 5x7: skip-count 5, 10, 15, ...
    'mul_skip_ten': SKIP_LINE,    # 10x7: skip-count by ten
    'mul_square': ARRAY,          # 7x7: a literal square array
    'mul_nine': ARRAY,            # 9x6: ten rows minus one row
    'mul_break_apart': ARRAY,     # 7x8 = 7x5 + 7x3: split the area
    # division
    'div_zero': GROUPS,           # 0/5: nothing to share out
    'div_by_one': GROUPS,         # 7/1: one group holds it all
    'div_self': GROUPS,           # 7/7: one each, so one group
    'div_halve': GROUPS,          # n/2: share into two equal groups
    'div_share': GROUPS,          # n/3, n/4: deal into equal groups
    'div_by_five': SKIP_LINE,     # 35/5: how many hops of five?
    'div_by_ten': SKIP_LINE,      # 70/10: how many hops of ten?
    'div_square': ARRAY,          # 49/7: the square array, one side known
    'div_think_mul': ARRAY,       # 56/7: 7 rows of what makes 56?
}

STAGE_LABELS = {
    1: 'Addition within 5',
    2: 'Subtraction within 5',
    3: 'Addition: sums to 10',
    4: 'Subtraction within 10',
    5: 'Tens & teens (no regrouping)',
    6: 'Teen subtraction (no regrouping)',
    7: 'Addition: bridging ten',
    8: 'Subtraction: through ten',
    9: 'Multiplication: ×0, ×1, ×10',
    10: 'Multiplication: ×2 (doubling)',
    11: 'Multiplication: ×5 (skip counting)',
    12: 'Multiplication: ×3 and ×4',
    13: 'Multiplication: squares',
    14: 'Multiplication: the tricky ones',
    15: 'Division: ÷1, ÷10 and by itself',
    16: 'Division: ÷2 (halving)',
    17: 'Division: ÷5',
    18: 'Division: ÷3 and ÷4',
    19: 'Division: squares',
    20: 'Division: the tricky ones',
}

# Which teaching batches belong to which operation (derived, kept for the
# report so a batch list can be filtered without touching the DB).
STAGES_BY_OP = {
    'add': (1, 3, 5, 7),
    'sub': (2, 4, 6, 8),
    'mul': (9, 10, 11, 12, 13, 14),
    'div': (15, 16, 17, 18, 19, 20),
}


def strategy_for(operation, a, b):
    """Return the strategy id (drives the visual model). Check order is
    precedence."""
    if operation == 'add':
        return _strategy_add(a, b)
    if operation == 'sub':
        return _strategy_sub(a, b)
    if operation == 'mul':
        return _strategy_mul(a, b)
    if operation == 'div':
        return _strategy_div(a, b)
    raise ValueError(f'unknown operation: {operation}')


def stage_for(operation, a, b):
    """Return the teaching batch for a fact. Magnitude first: every within-ten
    fact (stages 1-4) precedes every teen-result fact (5-8), and all of
    addition/subtraction precedes multiplication (9-14) and division (15-20)."""
    if operation == 'add':
        s, hi = a + b, max(a, b)
        if hi <= 5:          # both addends 0-5
            return 1
        if s <= 10:          # rest of the sums-to-10 facts (one addend 6-10)
            return 3
        if hi >= 10:         # teen result with a 10-19 addend: place value, no bridge
            return 5
        return 7             # both addends <= 9, sum 11-20: bridging ten
    if operation == 'sub':
        # (invariant from generation: 0 <= b <= a <= 20)
        if a <= 5:
            return 2
        if a <= 10:
            return 4
        if b == 10 or b <= a % 10 or (a - b) >= 10:   # teen minuend, no ten-crossing
            return 6
        return 8                                      # regroups through ten
    if operation == 'mul':
        return _stage_mul(a, b)
    if operation == 'div':
        return _stage_div(a, b)
    raise ValueError(f'unknown operation: {operation}')


def answer_max(operation):
    """Largest answer this operation can ask for."""
    return ANSWER_MAX[operation]


def keypad_for(operation):
    """'direct' (a button per number) or 'digits' (a 0-9 pad)."""
    return KEYPAD[operation]


# ------------------------------------------------------------------ add / sub

def _strategy_add(a, b):
    lo, hi = min(a, b), max(a, b)
    if lo == 0:
        return 'add_zero'
    if lo == 1:
        return 'count_on_1'
    if lo == 2:
        return 'count_on_2'
    if a == b:
        return 'doubles'
    if a + b == 10:
        return 'combos_of_10'
    if hi == 10:
        return 'plus_ten'
    if hi > 10:
        return 'teen_structure'
    if abs(a - b) == 1:
        return 'near_doubles'
    if a + b > 10:
        return 'make_ten'
    return 'add_within_10'


def _strategy_sub(a, b):
    if b == 0 or a == b:
        return 'sub_zero'
    if b == 1:
        return 'count_back_1'
    if b == 2:
        return 'count_back_2'
    if a - b <= 2:
        return 'count_up'
    if a == 2 * b:
        return 'halves'
    if a == 10:
        return 'subtract_from_10'
    if a > 10:
        ones = a % 10  # 0 for a == 20
        if b == 10:
            return 'minus_ten'
        if b == ones:
            return 'teens_minus_ones'
        if b < ones:
            return 'teen_parts'
        if b >= 7 or ones == 0:
            return 'take_from_ten'
        return 'back_to_ten'
    return 'think_addition'


# ------------------------------------------------------------ multiplication

def _strategy_mul(a, b):
    """Families are keyed on the *smaller* factor — that is the one you count
    groups of / skip-count by — with the harder 6-9 facts falling through to
    the area model."""
    lo, hi = min(a, b), max(a, b)
    if lo == 0:
        return 'mul_zero'
    if hi == 10:
        return 'mul_skip_ten'      # before mul_one so 1x10 skip-counts
    if lo == 1:
        return 'mul_one'
    if lo == 2:
        return 'mul_double'
    if lo == 5:
        return 'mul_skip_five'
    if lo in (3, 4):
        return 'mul_groups'
    if a == b:
        return 'mul_square'        # 6x6 .. 9x9
    if hi == 9:
        return 'mul_nine'          # 9x6, 9x7, 9x8: ten rows less one
    return 'mul_break_apart'       # 6x7, 6x8, 7x8 and their partners


def _stage_mul(a, b):
    lo, hi = min(a, b), max(a, b)
    if lo <= 1 or hi == 10:
        return 9
    if lo == 2:
        return 10
    if lo == 5:
        return 11
    if lo in (3, 4):
        return 12
    if a == b:
        return 13
    return 14


# ------------------------------------------------------------------ division

def _quotient(a, b):
    if b == 0:
        raise ValueError('division by zero is not a fact')
    return a // b


def _strategy_div(a, b):
    """`a / b`: b is the divisor (the group size or number of groups), and the
    answer is the missing factor."""
    q = _quotient(a, b)
    if a == 0:
        return 'div_zero'
    if b == 1:
        return 'div_by_one'
    if b == 10:
        return 'div_by_ten'
    if a == b:
        return 'div_self'
    if b == 2:
        return 'div_halve'
    if b == 5:
        return 'div_by_five'
    if b in (3, 4):
        return 'div_share'
    if q == b:
        return 'div_square'        # 36/6, 49/7, 64/8, 81/9
    return 'div_think_mul'


def _stage_div(a, b):
    q = _quotient(a, b)
    if b in (1, 10) or a == 0 or a == b:
        return 15
    if b == 2:
        return 16
    if b == 5:
        return 17
    if b in (3, 4):
        return 18
    if q == b:
        return 19
    return 20


# -------------------------------------------------------------------- order

def _canonical_key(operation, a, b):
    """A stable, arbitrary order for the facts of one batch. It only has to be
    deterministic — the scatter below is what decides the real sequence."""
    if operation == 'add':
        return (a + b, a)
    if operation == 'sub':
        return (a, b)
    if operation == 'mul':
        return (max(a, b), min(a, b), a)
    q = _quotient(a, b)
    return (max(q, b), min(q, b), b)


# Fixed so `intro_order` is reproducible: seed_facts is idempotent and a rerun
# must not renumber the sequence out from under students mid-learning.
SCATTER_SEED = 20260910


def _spread(facts, answer_of, rng):
    """Reorder so consecutive facts don't share an answer, *without* falling
    into a pattern.

    Picking the largest remaining answer-group every time does avoid runs, but
    it is completely deterministic and comes out as a sawtooth — batch 7 became
    "11 12 11 13 12 11 14 13 12 11 ...", which is no more varied to practise
    than the runs were. So the next answer is drawn at random from the groups
    still holding facts, weighted by how many each has left.

    The one forced move: if a single answer accounts for more than half of what
    remains, take it now. Otherwise it gets stranded and has to be emitted as a
    run at the tail, which is the exact thing being avoided.
    """
    groups = {}
    for f in facts:
        groups.setdefault(answer_of(f), []).append(f)
    out, last = [], None
    remaining = len(facts)
    while remaining:
        live = sorted(k for k, v in groups.items() if v)     # sorted: reproducible
        must = [k for k in live if k != last and len(groups[k]) * 2 > remaining]
        options = must or [k for k in live if k != last] or live
        pick = rng.choices(options, weights=[len(groups[k]) for k in options])[0]
        out.append(groups[pick].pop(0))
        last = pick
        remaining -= 1
    return out


def _order_batch(facts):
    """Order the facts inside one teaching batch.

    **The batch is the bucket.** Everything in it is the same kind of fact by
    construction — batch 7 is "addition that bridges ten", batch 12 is "the
    threes and fours" — so marching through it in a strict order buys no
    pedagogy and costs a lot of variety. Sorting addition by sum, which is what
    this used to do, made the sum *the sort key*: a student met all eight ways
    to answer 11, then all seven ways to answer 12, and so on in runs.

    So the batch is shuffled with a fixed seed and then spread so that
    consecutive facts answer differently. Progression lives entirely in the
    batch order (`stage_for`), which is where it belongs.
    """
    operation = facts[0][0]
    ordered = sorted(facts, key=lambda f: _canonical_key(operation, f[1], f[2]))
    rng = random.Random(f'{SCATTER_SEED}:{operation}:{len(ordered)}')
    rng.shuffle(ordered)
    return _spread(ordered, answer_of=lambda f: f[3], rng=rng)


def _domain(operation):
    """Every (a, b, answer) triple drilled for one operation."""
    if operation == 'add':
        return [(a, b, a + b)
                for a in range(21) for b in range(21) if a + b <= 20]
    if operation == 'sub':
        return [(a, b, a - b)
                for a in range(21) for b in range(21) if b <= a]
    if operation == 'mul':
        return [(a, b, a * b)
                for a in range(MUL_MAX + 1) for b in range(MUL_MAX + 1)]
    if operation == 'div':
        # b is the divisor (never 0); the quotient stays inside the tables
        return [(b * q, b, q)
                for b in range(1, MUL_MAX + 1) for q in range(MUL_MAX + 1)]
    raise ValueError(f'unknown operation: {operation}')


OPERATIONS = ('add', 'sub', 'mul', 'div')


def teaching_sequence(operations=OPERATIONS):
    """All facts in the exact order they should be introduced: batch by batch
    (`stage_for`), scattered inside each batch (`_order_batch`)."""
    batches = {}
    for op in operations:
        for a, b, answer in _domain(op):
            batches.setdefault(stage_for(op, a, b), []).append((op, a, b, answer))
    sequence = []
    for stage in sorted(batches):
        sequence.extend(_order_batch(batches[stage]))
    return sequence


def generate_facts(operations=OPERATIONS):
    """Yield (operation, a, b, answer, strategy, stage, intro_order) for the
    full four-operation domain, in teaching order."""
    for intro_order, (op, a, b, answer) in enumerate(teaching_sequence(operations)):
        yield (op, a, b, answer, strategy_for(op, a, b), stage_for(op, a, b),
               intro_order)


# --------------------------------------------------------------- report grids
#
# How each operation's facts are laid out on the progress page. Addition,
# subtraction and multiplication are the obvious table (row = a, column = b,
# cell = the answer). Division can't be: its dividend runs to 100, so a
# dividend axis would be a 101-row strip. Instead a division grid is the
# multiplication table read backwards — row = divisor, column = the answer —
# and the cell shows the number being divided.

GRID_SPECS = {
    'add': {
        'rows': list(range(21)), 'cols': list(range(21)),
        'row_head': 'first number', 'col_head': 'second number', 'note': '',
    },
    'sub': {
        'rows': list(range(21)), 'cols': list(range(21)),
        'row_head': 'first number', 'col_head': 'second number', 'note': '',
    },
    'mul': {
        'rows': list(range(MUL_MAX + 1)), 'cols': list(range(MUL_MAX + 1)),
        'row_head': 'first factor', 'col_head': 'second factor', 'note': '',
    },
    'div': {
        'rows': list(range(1, MUL_MAX + 1)), 'cols': list(range(MUL_MAX + 1)),
        'row_head': 'divisor', 'col_head': 'answer',
        'note': ('Rows are what you divide by, columns are the answer, and each '
                 'cell is the number being divided — so row 7, column 8 is '
                 '56 ÷ 7 = 8.'),
    },
}


def grid_cell(operation, a, b, answer):
    """(row, column) of a fact in its operation's grid."""
    if operation == 'div':
        return (b, answer)      # divisor down the side, answer across the top
    return (a, b)


def grid_label(operation, a, b, answer):
    """What to print in the fact's cell: the answer, except for division where
    the answer is already the column header — there the dividend is the useful
    number to see."""
    return a if operation == 'div' else answer


def grid_spec(operation):
    return GRID_SPECS[operation]
