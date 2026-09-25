from django.conf import settings
from django.db import models

from .strategies import OPERATIONS as ALL_OPERATIONS

OP_SYMBOLS = {'add': '+', 'sub': '−', 'mul': '×', 'div': '÷'}
OP_NAMES = {'add': 'Addition', 'sub': 'Subtraction',
            'mul': 'Multiplication', 'div': 'Division'}
# canonical display/teaching order for the four operations
OP_ORDER = list(ALL_OPERATIONS)

DEFAULT_OPERATIONS = ['add', 'sub']


def default_operations():
    """Callable (not a literal) so migrations serialize it and every Student
    gets its own list."""
    return list(DEFAULT_OPERATIONS)


def clean_operations(values):
    """Keep only real operation codes, in canonical order, without
    duplicates. Returns [] if nothing valid was given."""
    given = set(values or [])
    return [op for op in OP_ORDER if op in given]


class Fact(models.Model):
    """A single math fact (e.g. 9 + 4 = 13), seeded by `seed_facts`."""

    OPERATIONS = [(op, OP_NAMES[op]) for op in OP_ORDER]

    operation = models.CharField(max_length=3, choices=OPERATIONS)
    a = models.PositiveSmallIntegerField()
    b = models.PositiveSmallIntegerField()
    answer = models.PositiveSmallIntegerField()
    strategy = models.CharField(max_length=32)
    stage = models.PositiveSmallIntegerField(db_index=True)  # teaching batch 1-20
    intro_order = models.PositiveSmallIntegerField(default=0, db_index=True)  # SRS introduces in this order

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['operation', 'a', 'b'], name='unique_fact'),
        ]
        ordering = ['intro_order']

    @property
    def symbol(self):
        return OP_SYMBOLS[self.operation]

    def __str__(self):
        return f'{self.a} {self.symbol} {self.b} = {self.answer}'


class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    theme = models.CharField(max_length=32, default='pirate')
    # which of the four operations this student practices, set by a teacher on
    # the "Manage students" page. Facts outside these are never served, and the
    # progress report hides them — but their FactProgress rows are kept, so
    # turning an operation back on resumes exactly where the student left off.
    operations = models.JSONField(default=default_operations, blank=True)
    # ~15 min of real answering; see srs.POINTS for how points accrue.
    daily_goal_points = models.PositiveSmallIntegerField(default=150)
    # the how-to-play modal auto-shows once, on first login
    seen_instructions = models.BooleanField(default=False)
    # fact ids the student last chose for self-selected ("just these") practice
    custom_selection = models.JSONField(default=list, blank=True)
    # Which teaching batch new facts are currently drawn from — the scheduler's
    # running estimate of where this student actually is, not a record of what
    # they have been taught. It climbs whenever a new fact turns out to be
    # already known and drops when one is missed, so a student who arrives
    # already fluent at "n + 1" is not walked through every batch. See
    # srs._next_new_fact / srs.apply_answer.
    reach = models.PositiveSmallIntegerField(default=1)
    # A short-memory "how is it going right now" counter: up on a miss, down on
    # a correct answer. The scheduler reads it to hand back a fact the student
    # can do after a run of misses — placement that only ever escalates is how
    # a child ends up answering 89% of questions wrong and stops trying.
    recent_misses = models.PositiveSmallIntegerField(default=0)

    @property
    def enabled_operations(self):
        """The student's operations, validated and in canonical order. Falls
        back to the default pair if the stored value is empty or junk, so a
        student can never end up with nothing to practice."""
        return clean_operations(self.operations) or list(DEFAULT_OPERATIONS)

    def practices(self, operation):
        return operation in self.enabled_operations

    def __str__(self):
        return self.user.username


class FactProgress(models.Model):
    """Per-student SRS state for one fact."""

    SCAFFOLD_FULL = 2      # visual model shown immediately
    SCAFFOLD_FADING = 1    # model appears only after a delay or a miss
    SCAFFOLD_NONE = 0      # no model — the goal state

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='progress')
    fact = models.ForeignKey(Fact, on_delete=models.CASCADE)
    box = models.PositiveSmallIntegerField(default=0)
    scaffold = models.PositiveSmallIntegerField(default=SCAFFOLD_FULL)
    scaffold_streak = models.PositiveSmallIntegerField(default=0)  # fluent corrects at current scaffold
    due_at = models.DateTimeField(db_index=True)
    introduced_at = models.DateTimeField()
    streak = models.PositiveSmallIntegerField(default=0)
    lapses = models.PositiveSmallIntegerField(default=0)
    ema_ms = models.PositiveIntegerField(null=True, blank=True)  # smoothed response time
    mastered = models.BooleanField(default=False)
    # Answered correctly *and* fast on the very first exposure: evidence the
    # student already had it, so it skips most of the Leitner ladder. Also what
    # the placement ladder reads to decide the student is above this batch.
    known_on_sight = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'fact'], name='unique_student_fact'),
        ]

    def __str__(self):
        return f'{self.student} · {self.fact} · box {self.box}'


class Attempt(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attempts')
    fact = models.ForeignKey(Fact, on_delete=models.CASCADE)
    # None = the pace bar ran out before the student answered (scored as a miss)
    given_answer = models.SmallIntegerField(null=True, blank=True)
    correct = models.BooleanField()
    response_ms = models.PositiveIntegerField()
    scaffold_shown = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        mark = '✓' if self.correct else '✗'
        given = '⌛' if self.given_answer is None else self.given_answer
        return f'{self.student} · {self.fact} → {given} {mark}'


class DailyProgress(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='days')
    date = models.DateField()
    points = models.PositiveIntegerField(default=0)
    questions = models.PositiveIntegerField(default=0)
    goal_met = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'date'], name='unique_student_date'),
        ]

    def __str__(self):
        return f'{self.student} · {self.date} · {self.points} pts'
