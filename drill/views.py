import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import srs
from .models import Attempt, DailyProgress, Fact, FactProgress, Student
from .strategies import STRATEGY_MODEL
from .themes import THEMES, get_theme


def _student(request) -> Student:
    student, _ = Student.objects.get_or_create(user=request.user)
    return student


def _theme_context(student):
    theme = get_theme(student.theme)
    return {
        'student': student,
        'theme': theme,
        'theme_key': student.theme if student.theme in THEMES else 'pirate',
        'themes': THEMES,
    }


# ---------------------------------------------------------------- pages

@login_required
def home(request):
    student = _student(request)
    today = _today(student)
    ctx = _theme_context(student)
    # Auto-show the how-to-play modal once, on first login.
    first_time = not student.seen_instructions
    if first_time:
        student.seen_instructions = True
        student.save(update_fields=['seen_instructions'])
    ctx.update({
        'daily': _daily_dict(student, today),
        'streak': _streak(student),
        'mastered_count': student.progress.filter(mastered=True).count(),
        'total_facts': Fact.objects.count(),
        'show_instructions': first_time,
        'instructions': _instructions(ctx['theme'], student.daily_goal_points),
    })
    return render(request, 'drill/home.html', ctx)


def _instructions(theme, goal):
    """Theme-flavored how-to-play content. The intro speaks the theme's
    language (coins / energy / jewels); the steps are shared but name the
    theme's currency."""
    points = theme['points_name']
    return {
        'title': theme['instructions_title'],
        'intro': theme['instructions_intro'].format(goal=goal),
        'steps': [
            ('🔢', 'Tap any number from 0 to 20, or type it and press Enter.'),
            ('👀', 'Pictures such as ten-frames and number lines help you see the '
                   'math. They fade away as you get faster.'),
            ('⚡', f'Answer quickly to earn the most {points}! Aim to solve every '
                   'fact in under 5 seconds with no picture.'),
            ('📅', f'Practice a little every day, and the bar at the top fills up '
                   f'as you collect {points}.'),
        ],
    }


@login_required
@ensure_csrf_cookie  # guarantee the csrftoken cookie exists for the JS POSTs
def practice(request):
    student = _student(request)
    ctx = _theme_context(student)
    # Pass a dict to json_script (it serializes); do NOT pre-dump to a string
    # or it gets double-encoded and THEME becomes a string in the browser.
    ctx['theme_data'] = {
        'key': ctx['theme_key'],
        'cheers': ctx['theme']['cheers'],
        'oops': ctx['theme']['oops'],
        'goal_met': ctx['theme']['goal_met'],
        'point_icon': ctx['theme']['point_icon'],
    }
    return render(request, 'drill/practice.html', ctx)


@login_required
def progress(request):
    student = _student(request)
    ctx = _theme_context(student)
    ctx.update(_build_report(student))
    return render(request, 'drill/progress.html', ctx)


@staff_member_required
def report(request, username):
    user = get_object_or_404(User, username=username)
    target, _ = Student.objects.get_or_create(user=user)
    viewer = _student(request)
    ctx = _theme_context(viewer)
    ctx.update(_build_report(target))
    ctx['report_for'] = target
    return render(request, 'drill/progress.html', ctx)


@login_required
@require_POST
def set_theme(request):
    student = _student(request)
    theme = request.POST.get('theme', '')
    if theme in THEMES:
        student.theme = theme
        student.save(update_fields=['theme'])
    return redirect('home')


# ---------------------------------------------------------------- teacher tools

@staff_member_required
def manage(request):
    """Teacher dashboard: add students, reset their passwords, jump to reports.
    Students are created here or via `manage.py create_student`, never by
    self-signup, and never with an email."""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_student':
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            theme = request.POST.get('theme', 'pirate')
            goal = request.POST.get('goal') or 150
            if not username or not password:
                messages.error(request, 'Username and password are both required.')
            elif User.objects.filter(username=username).exists():
                messages.error(request, f'A user named “{username}” already exists.')
            elif theme not in THEMES:
                messages.error(request, 'Unknown theme.')
            else:
                user = User.objects.create_user(username=username, password=password)
                Student.objects.create(
                    user=user, theme=theme, daily_goal_points=int(goal))
                messages.success(request, f'Student “{username}” added.')
        elif action == 'reset_password':
            target = get_object_or_404(Student, pk=request.POST.get('student_id'))
            new_password = request.POST.get('password', '')
            if len(new_password) < 4:
                messages.error(request, 'Password must be at least 4 characters.')
            else:
                target.user.set_password(new_password)
                target.user.save()
                messages.success(
                    request, f'Password reset for “{target.user.username}”.')
        return redirect('manage')

    students = (Student.objects.select_related('user')
                .annotate(mastered=Count('progress', filter=Q(progress__mastered=True)))
                .order_by('user__username'))
    ctx = _theme_context(_student(request))
    ctx.update({
        'students': students,
        'total_facts': Fact.objects.count(),
        'is_manage': True,
    })
    return render(request, 'drill/manage.html', ctx)


# ---------------------------------------------------------------- API

@login_required
@require_GET
def api_next(request):
    student = _student(request)
    now = timezone.now()
    prog = srs.next_question(
        student, exclude_fact_id=request.session.get('last_fact_id'), now=now)
    request.session['served'] = {'fact_id': prog.fact_id, 'at': now.timestamp()}
    fact = prog.fact
    return JsonResponse({
        'fact_id': fact.id,
        'op': fact.operation,
        'symbol': fact.symbol,
        'a': fact.a,
        'b': fact.b,
        'scaffold': prog.scaffold,
        'model': STRATEGY_MODEL[fact.strategy],
        'strategy': fact.strategy,
        'pace_ms': srs.FLUENT_MS[prog.scaffold],  # the real fluency window
        'daily': _daily_dict(student, _today(student)),
    })


@login_required
@require_POST
def api_answer(request):
    student = _student(request)
    now = timezone.now()
    try:
        body = json.loads(request.body)
        fact_id = int(body['fact_id'])
        given = int(body['answer'])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return HttpResponseBadRequest('bad payload')

    served = request.session.get('served')
    if not served or served['fact_id'] != fact_id:
        return HttpResponseBadRequest('answer does not match the served question')
    del request.session['served']

    # Server-side timing: elapsed since we served the question. The client
    # can't fake fluency by reporting a small number.
    response_ms = int((now.timestamp() - served['at']) * 1000)

    prog = get_object_or_404(
        FactProgress.objects.select_related('fact'), student=student, fact_id=fact_id)
    correct = (given == prog.fact.answer)

    Attempt.objects.create(
        student=student, fact=prog.fact, given_answer=given, correct=correct,
        response_ms=min(max(response_ms, 1), srs.MAX_RESPONSE_MS),
        scaffold_shown=prog.scaffold)

    points, mastered_now = srs.apply_answer(prog, correct, response_ms, now=now)
    request.session['last_fact_id'] = fact_id

    today = _today(student)
    daily, _ = DailyProgress.objects.get_or_create(student=student, date=today)
    goal_just_met = False
    daily.points += points
    daily.questions += 1
    if not daily.goal_met and daily.points >= student.daily_goal_points:
        daily.goal_met = True
        goal_just_met = True
    daily.save()

    return JsonResponse({
        'correct': correct,
        'answer': prog.fact.answer,
        'points_earned': points,
        'mastered_now': mastered_now,
        'goal_just_met': goal_just_met,
        'daily': _daily_dict(student, today, daily=daily),
    })


# ---------------------------------------------------------------- helpers

def _today(student):
    return timezone.localdate()


def _daily_dict(student, today, daily=None):
    if daily is None:
        daily = DailyProgress.objects.filter(student=student, date=today).first()
    points = daily.points if daily else 0
    return {
        'points': points,
        'goal': student.daily_goal_points,
        'met': bool(daily and daily.goal_met),
        'questions': daily.questions if daily else 0,
    }


def _streak(student):
    """Consecutive goal-met days ending today (or yesterday, so the streak
    doesn't read as broken before today's practice)."""
    met = set(DailyProgress.objects.filter(student=student, goal_met=True)
              .values_list('date', flat=True))
    if not met:
        return 0
    day = timezone.localdate()
    if day not in met:
        day -= timedelta(days=1)
    streak = 0
    while day in met:
        streak += 1
        day -= timedelta(days=1)
    return streak


STATUS_LABELS = {
    'new': 'Not started',
    'learning': 'Learning',
    'developing': 'Getting there',
    'known': 'Known',
    'mastered': 'Mastered',
}


def _status(prog):
    if prog is None:
        return 'new'
    if prog.mastered:
        return 'mastered'
    if prog.box >= srs.MASTERY_BOX:
        return 'known'
    if prog.box > srs.LEARNING_BOX_MAX:
        return 'developing'
    return 'learning'


def _build_report(student):
    by_fact = {p.fact_id: p for p in student.progress.all()}
    facts = Fact.objects.all()
    grids = {}
    counts = {key: 0 for key in STATUS_LABELS}
    for op in ('add', 'sub'):
        cells = {}
        for f in facts:
            if f.operation != op:
                continue
            status = _status(by_fact.get(f.id))
            counts[status] += 1
            cells[(f.a, f.b)] = {'status': status, 'label': str(f),
                                 'title': f'{f} · {STATUS_LABELS[status]}'}
        rows = []
        for a in range(21):
            row = [cells.get((a, b)) for b in range(21)]
            if any(row):
                rows.append({'a': a, 'cells': row})
        grids[op] = rows
    total = sum(counts.values())
    recent = (Attempt.objects
              .filter(student=student, correct=True)
              .order_by('-created_at')[:50]
              .aggregate(avg=Avg('response_ms')))
    return {
        'grids': grids,
        'cols': list(range(21)),
        'counts': counts,
        'legend': [{'key': k, 'label': label, 'count': counts[k]}
                   for k, label in STATUS_LABELS.items()],
        'status_labels': STATUS_LABELS,
        'total_facts': total,
        'mastered_count': counts['mastered'],
        'streak': _streak(student),
        'avg_recent_s': round(recent['avg'] / 1000, 1) if recent['avg'] else None,
    }
