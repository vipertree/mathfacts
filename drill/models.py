from django.conf import settings
from django.db import models

OP_SYMBOLS = {'add': '+', 'sub': '−'}


class Fact(models.Model):
    """A single math fact (e.g. 9 + 4 = 13), seeded by `seed_facts`."""

    OPERATIONS = [
        ('add', 'Addition'),
        ('sub', 'Subtraction'),
        # future: ('mul', 'Multiplication'), ('div', 'Division')
    ]

    operation = models.CharField(max_length=3, choices=OPERATIONS)
    a = models.PositiveSmallIntegerField()
    b = models.PositiveSmallIntegerField()
    answer = models.PositiveSmallIntegerField()
    strategy = models.CharField(max_length=32)
    stage = models.PositiveSmallIntegerField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['operation', 'a', 'b'], name='unique_fact'),
        ]
        ordering = ['stage', 'operation', 'a', 'b']

    @property
    def symbol(self):
        return OP_SYMBOLS[self.operation]

    def __str__(self):
        return f'{self.a} {self.symbol} {self.b} = {self.answer}'


class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    theme = models.CharField(max_length=32, default='pirate')
    # ~15 min of real answering; see srs.POINTS for how points accrue.
    daily_goal_points = models.PositiveSmallIntegerField(default=150)
    # the how-to-play modal auto-shows once, on first login
    seen_instructions = models.BooleanField(default=False)

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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'fact'], name='unique_student_fact'),
        ]

    def __str__(self):
        return f'{self.student} · {self.fact} · box {self.box}'


class Attempt(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attempts')
    fact = models.ForeignKey(Fact, on_delete=models.CASCADE)
    given_answer = models.SmallIntegerField()
    correct = models.BooleanField()
    response_ms = models.PositiveIntegerField()
    scaffold_shown = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        mark = '✓' if self.correct else '✗'
        return f'{self.student} · {self.fact} → {self.given_answer} {mark}'


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
