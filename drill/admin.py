from django.contrib import admin

from .models import Attempt, DailyProgress, Fact, FactProgress, Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['user', 'theme', 'daily_goal_points']
    list_editable = ['theme', 'daily_goal_points']
    raw_id_fields = ['user']


@admin.register(Fact)
class FactAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'operation', 'strategy', 'stage']
    list_filter = ['operation', 'strategy', 'stage']
    search_fields = ['a', 'b']

    def has_add_permission(self, request):
        return False  # facts come from seed_facts


@admin.register(FactProgress)
class FactProgressAdmin(admin.ModelAdmin):
    list_display = ['student', 'fact', 'box', 'scaffold', 'ema_ms', 'mastered', 'due_at']
    list_filter = ['mastered', 'box', 'student']
    raw_id_fields = ['student', 'fact']


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'student', 'fact', 'given_answer', 'correct',
                    'response_ms', 'scaffold_shown']
    list_filter = ['correct', 'student']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DailyProgress)
class DailyProgressAdmin(admin.ModelAdmin):
    list_display = ['date', 'student', 'points', 'questions', 'goal_met']
    list_filter = ['goal_met', 'student']
    date_hierarchy = 'date'
