"""
Two independent things are decided here for every fact:

1. **strategy** (``strategy_for``) — the mental strategy we want the visual
   model to evoke (make-ten, near-doubles, back-to-ten, ...). ``STRATEGY_MODEL``
   maps each strategy to the picture that best shows it. This drives *what the
   student sees*, not when they see it.

2. **teaching order** (``stage_for`` + ``generate_facts``) — *when* a fact is
   introduced. Order is driven by **magnitude first**, not by strategy: all
   facts within ten come before any teen-result fact, so a trivial ``14 + 0``
   never appears before ``5 + 5``. Batches are broad and mix strategies inside
   them, so practice stays varied instead of grinding "+0, then +1, then +2".

   The eight batches (``STAGE_LABELS``):
     1 add, both addends 0-5            (sums to 10, small)
     2 sub, minuend 0-5
     3 add, rest of sums to 10          (one addend 6-10, e.g. 7+3, 9+1)
     4 sub, minuend 6-10
     5 add, teen result with a 10-19 addend (place value: 13+4, 10+6, no bridge)
     6 sub, teen minuend, no regrouping (17-5, 19-3, 17-10)
     7 add, teen result, both addends <=9 (bridging ten: 9+4, 8+6, doubles)
     8 sub, teen minuend, regrouping    (13-5, 14-9, 12-6)

   Within a batch facts are ordered by total/magnitude with the balanced ones
   (doubles, halves) first and the trivial +0/-0 ones last, which keeps the
   opening varied. The absolute sequence position is stored as ``intro_order``
   and is what the SRS introduces in.

Extending to multiplication/division later = new branches in strategy_for /
stage_for; nothing else in the app hard-codes the current set.
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

STAGE_LABELS = {
    1: 'Addition within 5',
    2: 'Subtraction within 5',
    3: 'Addition: sums to 10',
    4: 'Subtraction within 10',
    5: 'Tens & teens (no regrouping)',
    6: 'Teen subtraction (no regrouping)',
    7: 'Addition: bridging ten',
    8: 'Subtraction: through ten',
}


def strategy_for(operation, a, b):
    """Return the strategy id (drives the visual model). Check order is
    precedence."""
    if operation == 'add':
        return _strategy_add(a, b)
    if operation == 'sub':
        return _strategy_sub(a, b)
    raise ValueError(f'unknown operation: {operation}')


def stage_for(operation, a, b):
    """Return the teaching batch (1-8) for a fact. Magnitude first: every
    within-ten fact (stages 1-4) precedes every teen-result fact (5-8)."""
    if operation == 'add':
        s, hi = a + b, max(a, b)
        if hi <= 5:          # both addends 0-5
            return 1
        if s <= 10:          # rest of the sums-to-10 facts (one addend 6-10)
            return 3
        if hi >= 10:         # teen result with a 10-19 addend: place value, no bridge
            return 5
        return 7             # both addends <= 9, sum 11-20: bridging ten
    # subtraction (invariant from generation: 0 <= b <= a <= 20)
    if a <= 5:
        return 2
    if a <= 10:
        return 4
    if b == 10 or b <= a % 10 or (a - b) >= 10:   # teen minuend, no ten-crossing
        return 6
    return 8                                       # teen minuend, regroups through ten


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


def _within_batch_key(operation, a, b):
    """Order inside a batch: grow by total/magnitude, put the balanced facts
    (doubles, halves) first and the trivial +0 / -0 facts last, so the opening
    of each batch is varied rather than a run of zero facts."""
    if operation == 'add':
        return (a + b, abs(a - b), a)
    # subtraction: minuend grows; within a minuend, 'halves' (b ~ a/2) first
    return (a, abs(a - 2 * b), b)


def teaching_sequence():
    """All facts in the exact order they should be introduced."""
    facts = []
    for a in range(21):
        for b in range(21):
            if a + b <= 20:
                facts.append(('add', a, b, a + b))
            if b <= a:
                facts.append(('sub', a, b, a - b))
    facts.sort(key=lambda f: (stage_for(f[0], f[1], f[2]),
                              _within_batch_key(f[0], f[1], f[2])))
    return facts


def generate_facts():
    """Yield (operation, a, b, answer, strategy, stage, intro_order) for the
    full addition/subtraction domain (sums/minuends <= 20), in teaching order."""
    for intro_order, (op, a, b, answer) in enumerate(teaching_sequence()):
        yield (op, a, b, answer, strategy_for(op, a, b), stage_for(op, a, b), intro_order)
