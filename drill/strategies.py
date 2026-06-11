"""
Strategy/stage classification for math facts.

Every fact gets a (strategy, stage) at seed time:

- ``strategy`` names the mental strategy we want the visual model to evoke
  (make-ten, near-doubles, back-to-ten, ...). STRATEGY_MODEL maps each
  strategy to the visual model that best depicts it.
- ``stage`` is the global teaching order. The SRS introduces new facts in
  stage order, interleaving subtraction right after the addition ideas it
  builds on (fact families: doubles -> halves, combos of 10 -> subtract
  from 10, make-ten -> bridging subtraction).

Extending to multiplication/division later = new operation branch in
classify() + new strategies/stages; nothing else in the app hard-codes
the current set.
"""

# Visual model ids understood by static/drill/js/models/*.js
TEN_FRAME = 'ten_frame'
NUMBER_LINE = 'number_line'
REKENREK = 'rekenrek'
BARS = 'bars'

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
}

# Teaching order. Numbers are global; subtraction follows the addition idea
# it leans on. (Stage values are persisted on Fact rows by seed_facts —
# reordering means reseeding.)
STAGES = {
    'add_zero': 1, 'count_on_1': 1,
    'sub_zero': 2, 'count_back_1': 2,
    'count_on_2': 3,
    'count_back_2': 4, 'count_up': 4,
    'doubles': 5,
    'halves': 6,
    'combos_of_10': 7,
    'subtract_from_10': 8,
    'plus_ten': 9, 'teen_structure': 9,
    'minus_ten': 10, 'teens_minus_ones': 10, 'teen_parts': 10,
    'near_doubles': 11,
    'add_within_10': 12,
    'think_addition': 13,
    'make_ten': 14,
    'back_to_ten': 15,
    'take_from_ten': 16,
}


def classify(operation, a, b):
    """Return (strategy, stage) for a fact. Order of checks is precedence."""
    if operation == 'add':
        strategy = _classify_add(a, b)
    elif operation == 'sub':
        strategy = _classify_sub(a, b)
    else:
        raise ValueError(f'unknown operation: {operation}')
    return strategy, STAGES[strategy]


def _classify_add(a, b):
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


def _classify_sub(a, b):
    # invariant from fact generation: 0 <= b <= a <= 20
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
        # crossing the ten (or subtracting from the full 20)
        if b >= 7 or ones == 0:
            return 'take_from_ten'
        return 'back_to_ten'
    return 'think_addition'


def generate_facts():
    """Yield (operation, a, b, answer, strategy, stage) for the full
    addition/subtraction domain with sums/minuends <= 20."""
    for a in range(21):
        for b in range(21):
            if a + b <= 20:
                strategy, stage = classify('add', a, b)
                yield ('add', a, b, a + b, strategy, stage)
            if b <= a:
                strategy, stage = classify('sub', a, b)
                yield ('sub', a, b, a - b, strategy, stage)
