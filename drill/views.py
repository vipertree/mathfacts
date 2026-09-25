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
from .models import (DEFAULT_OPERATIONS, OP_NAMES, OP_ORDER, OP_SYMBOLS,
                     Attempt, DailyProgress, Fact, FactProgress, Student,
                     clean_operations)
from .strategies import (STAGE_LABELS, STAGES_BY_OP, STRATEGY_MODEL,
                         answer_max, grid_cell, grid_label, grid_spec,
                         keypad_for)
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
    ops = student.enabled_operations
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
        'mastered_count': student.progress.filter(
            mastered=True, fact__operation__in=ops).count(),
        'total_facts': Fact.objects.filter(operation__in=ops).count(),
        'operations': [OP_NAMES[op] for op in ops],
        'show_instructions': first_time,
        'instructions': _instructions(ctx['theme'], student.daily_goal_points, ops),
        'custom_count': len(student.custom_selection or []),
    })
    return render(request, 'drill/home.html', ctx)


def _instructions(theme, goal, operations):
    """Theme-flavored how-to-play content. The intro speaks the theme's
    language (coins / energy / jewels); the steps are shared but name the
    theme's currency and the operations this student actually practices."""
    points = theme['points_name']
    pads = {keypad_for(op) for op in operations}
    widest = max(answer_max(op) for op in operations)
    if pads == {'direct'}:
        keypad = f'Tap any number from 0 to {widest}, or type it and press Enter.'
    elif pads == {'digits'}:
        keypad = ('Tap the digits to build your answer, then tap ⏎ (or press '
                  'Enter). ⌫ rubs out a digit.')
    else:
        keypad = ('For + and −, tap any number from 0 to 20. For × and ÷, tap '
                  'the digits to build your answer and then tap ⏎.')
    return {
        'title': theme['instructions_title'],
        'intro': theme['instructions_intro'].format(goal=goal),
        'steps': [
            ('🔢', keypad),
            ('👀', 'Pictures such as ten-frames, equal groups and arrays help you '
                   'see the math. They fade away as you get faster.'),
            ('⏳', 'Answer before the timer bar runs out. If it empties, that '
                   'one counts as a miss.'),
            ('⚡', f'Answer quickly to earn the most {points}! Aim to solve every '
                   'fact in under 5 seconds with no picture.'),
            ('📅', f'Practice a little every day, and the bar at the top fills up '
                   f'as you collect {points}.'),
        ],
    }


@login_required
@ensure_csrf_cookie  # guarantee the csrftoken cookie exists for the JS POSTs
def practice(request):
    """Normal SRS practice. The algorithm picks every question."""
    student = _student(request)
    request.session['practice_mode'] = 'srs'
    return _render_practice(request, student, custom=False)


@login_required
@ensure_csrf_cookie
def practice_custom(request):
    """Practice only the facts the student selected on the grid. Does not count
    toward the daily goal. Uses the saved selection (Student.custom_selection)."""
    student = _student(request)
    if not student.custom_selection:
        messages.info(request, 'Pick some facts on the grid first, then practice just those.')
        return redirect('progress')
    request.session['practice_mode'] = 'custom'
    return _render_practice(request, student, custom=True,
                            custom_count=len(student.custom_selection))


def _render_practice(request, student, custom, custom_count=0):
    ctx = _theme_context(student)
    ctx['custom'] = custom
    ctx['custom_count'] = custom_count
    # Pass a dict to json_script (it serializes); do NOT pre-dump to a string
    # or it gets double-encoded and THEME becomes a string in the browser.
    ctx['theme_data'] = {
        'key': ctx['theme_key'],
        'custom': custom,
        'cheers': ctx['theme']['cheers'],
        'oops': ctx['theme']['oops'],
        'goal_met': ctx['theme']['goal_met'],
        'point_icon': ctx['theme']['point_icon'],
    }
    return render(request, 'drill/practice.html', ctx)


@login_required
@require_POST
def select_facts(request):
    """Save the student's grid selection and launch custom practice."""
    student = _student(request)
    try:
        ids = [int(x) for x in request.POST.getlist('fact_ids')]
    except (TypeError, ValueError):
        return HttpResponseBadRequest('bad selection')
    valid = list(Fact.objects.filter(
        id__in=ids, operation__in=student.enabled_operations
    ).values_list('id', flat=True))
    student.custom_selection = valid
    student.save(update_fields=['custom_selection'])
    if not valid:
        messages.info(request, 'Select at least one fact to practice.')
        return redirect('progress')
    return redirect('practice_custom')


@login_required
def progress(request):
    student = _student(request)
    ctx = _theme_context(student)
    ctx.update(_build_report(student, can_select=True))
    return render(request, 'drill/progress.html', ctx)


@staff_member_required
def report(request, username):
    user = get_object_or_404(User, username=username)
    target, _ = Student.objects.get_or_create(user=user)
    viewer = _student(request)
    ctx = _theme_context(viewer)
    ctx.update(_build_report(target, can_select=False))
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
    """Teacher dashboard: add students, choose which of the four operations
    each one practices, reset their passwords, jump to reports. Students are
    created here or via `manage.py create_student`, never by self-signup, and
    never with an email."""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_student':
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            theme = request.POST.get('theme', 'pirate')
            goal = request.POST.get('goal') or 150
            operations = clean_operations(request.POST.getlist('operations'))
            if not username or not password:
                messages.error(request, 'Username and password are both required.')
            elif User.objects.filter(username=username).exists():
                messages.error(request, f'A user named “{username}” already exists.')
            elif theme not in THEMES:
                messages.error(request, 'Unknown theme.')
            elif not operations:
                messages.error(request, 'Pick at least one operation to practice.')
            else:
                user = User.objects.create_user(username=username, password=password)
                Student.objects.create(
                    user=user, theme=theme, daily_goal_points=int(goal),
                    operations=operations)
                messages.success(
                    request,
                    f'Student “{username}” added ({_op_summary(operations)}).')
        elif action == 'set_operations':
            target = get_object_or_404(Student, pk=request.POST.get('student_id'))
            operations = clean_operations(request.POST.getlist('operations'))
            if not operations:
                # Zero operations would leave the student with nothing to do.
                messages.error(
                    request,
                    f'“{target.user.username}” needs at least one operation — '
                    'nothing changed.')
            else:
                target.operations = operations
                target.save(update_fields=['operations'])
                # Drop any hand-picked facts that just left the assignment, so
                # "practice my set" can't resurrect them.
                _prune_selection(target)
                messages.success(
                    request,
                    f'“{target.user.username}” now practices '
                    f'{_op_summary(operations)}.')
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
    # Per-student: which operations are on, and how many of *their* facts are
    # mastered (the annotation above counts every operation, including ones
    # they no longer practice).
    totals = dict(Fact.objects.values_list('operation').annotate(n=Count('id')))
    rows = []
    for st in students:
        ops = st.enabled_operations
        rows.append({
            'student': st,
            'checks': [{'code': op, 'name': OP_NAMES[op],
                        'symbol': OP_SYMBOLS[op], 'on': op in ops}
                       for op in OP_ORDER],
            'mastered': st.progress.filter(
                mastered=True, fact__operation__in=ops).count(),
            'total': sum(totals.get(op, 0) for op in ops),
            'working_on': _working_on(st),
        })
    ctx = _theme_context(_student(request))
    ctx.update({
        'rows': rows,
        'op_choices': [{'code': op, 'name': OP_NAMES[op], 'symbol': OP_SYMBOLS[op],
                        'default': op in DEFAULT_OPERATIONS}
                       for op in OP_ORDER],
        'op_totals': [{'name': OP_NAMES[op], 'symbol': OP_SYMBOLS[op],
                       'count': totals.get(op, 0)} for op in OP_ORDER],
        'total_facts': Fact.objects.count(),
        'is_manage': True,
    })
    return render(request, 'drill/manage.html', ctx)


def _op_summary(operations):
    return ', '.join(OP_NAMES[op].lower() for op in operations)


def _working_on(student):
    """The batch the scheduler has placed this student at, for the teacher to
    sanity-check. `reach` can point at a batch outside the student's assigned
    operations (it is clamped at introduction time, not stored clamped), so
    report the nearest batch that is actually theirs."""
    mine = sorted(stage for op in student.enabled_operations
                  for stage in STAGES_BY_OP[op])
    if not mine:
        return ''
    at_or_below = [s for s in mine if s <= student.reach]
    stage = at_or_below[-1] if at_or_below else mine[0]
    return STAGE_LABELS[stage]


def _prune_selection(student):
    """Keep only self-selected facts that are still in the student's assigned
    operations."""
    if not student.custom_selection:
        return
    kept = list(Fact.objects.filter(
        id__in=student.custom_selection,
        operation__in=student.enabled_operations).values_list('id', flat=True))
    if len(kept) != len(student.custom_selection):
        student.custom_selection = kept
        student.save(update_fields=['custom_selection'])


# ---------------------------------------------------------------- API

@login_required
@require_GET
def api_next(request):
    student = _student(request)
    now = timezone.now()
    custom = request.session.get('practice_mode') == 'custom'
    exclude = request.session.get('last_fact_id')
    try:
        if custom:
            prog = srs.next_custom(student, student.custom_selection or [],
                                   exclude_fact_id=exclude, now=now)
        else:
            prog = srs.next_question(student, exclude_fact_id=exclude, now=now)
    except Fact.DoesNotExist:
        # No facts in the assigned operations (or an unseeded table). Tell the
        # client to stop asking instead of letting it spin on a 500.
        return JsonResponse({
            'empty': True,
            'message': 'Nothing to practice right now — ask your teacher '
                       'which math to work on.',
        })
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
        'answer_max': answer_max(fact.operation),
        'keypad': keypad_for(fact.operation),      # 'direct' or 'digits'
        # How many digits the answer has, so a typed answer submits the moment
        # it is complete: "5" for 5 x 1 is done, while 7 x 8 waits for the
        # second digit. This gives nothing away — the client is already holding
        # both operands and can do the arithmetic itself; the server still
        # scores and times the answer, which is what actually has to be trusted.
        'answer_digits': len(str(prog.fact.answer)),
        'custom': custom,
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
        # answer: null means the pace bar ran out before they answered
        given = None if body['answer'] is None else int(body['answer'])
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
    # Out of time is a miss, whether the client says so (answer: null) or the
    # answer simply arrives after the pace window closed.
    timed_out = (given is None or
                 response_ms > srs.FLUENT_MS[prog.scaffold] + srs.TIMEOUT_GRACE_MS)
    correct = (not timed_out and given == prog.fact.answer)

    Attempt.objects.create(
        student=student, fact=prog.fact, given_answer=given, correct=correct,
        response_ms=min(max(response_ms, 1), srs.MAX_RESPONSE_MS),
        scaffold_shown=prog.scaffold)

    # Practicing always improves the student's stats (box, scaffold, mastery)...
    points, mastered_now = srs.apply_answer(prog, correct, response_ms, now=now)
    request.session['last_fact_id'] = fact_id

    # ...but self-selected practice does NOT count toward the daily goal.
    today = _today(student)
    custom = request.session.get('practice_mode') == 'custom'
    goal_just_met = False
    if custom:
        points = 0
    else:
        daily, _ = DailyProgress.objects.get_or_create(student=student, date=today)
        daily.points += points
        daily.questions += 1
        if not daily.goal_met and daily.points >= student.daily_goal_points:
            daily.goal_met = True
            goal_just_met = True
        daily.save()

    return JsonResponse({
        'correct': correct,
        'timed_out': timed_out,
        'answer': prog.fact.answer,
        'points_earned': points,
        'mastered_now': mastered_now,
        'goal_just_met': goal_just_met,
        'custom': custom,
        'daily': _daily_dict(student, today),
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


# Four reporting levels, best to worst. PROFICIENT_BOX is the Leitner box at
# which a fact has survived multi-day reviews (day-scale intervals start at
# box 2; box 3+ means it has come back correct across days).
STATUS_LABELS = {
    'mastered': 'Mastered',
    'proficient': 'Proficient',
    'practice': 'Needs practice',
    'untested': 'Not tested yet',
}
STATUS_ORDER = ['mastered', 'proficient', 'practice', 'untested']
PROFICIENT_BOX = 3


def _status(prog):
    if prog is None:
        return 'untested'
    if prog.mastered:
        return 'mastered'
    if prog.box >= PROFICIENT_BOX:
        return 'proficient'
    return 'practice'


def _build_report(student, can_select=False):
    """The 4-level report, one grid per operation the student is assigned.

    Each operation brings its own axes (see strategies.GRID_SPECS): + - and x
    are the familiar row-by-column table, while division is laid out as
    divisor x answer with the dividend in the cell, because a dividend axis
    would run to 100.
    """
    ops = student.enabled_operations
    by_fact = {p.fact_id: p for p in student.progress.all()}
    facts = list(Fact.objects.filter(operation__in=ops))
    selected = set(student.custom_selection or [])
    grids = []
    counts = {key: 0 for key in STATUS_LABELS}
    # per-batch breakdown (teaching stage -> per-status counts)
    batches = {s: {'label': label, 'counts': {k: 0 for k in STATUS_LABELS}, 'total': 0}
               for s, label in STAGE_LABELS.items()}
    for op in ops:
        spec = grid_spec(op)
        cells = {}
        for f in facts:
            if f.operation != op:
                continue
            status = _status(by_fact.get(f.id))
            counts[status] += 1
            batches[f.stage]['counts'][status] += 1
            batches[f.stage]['total'] += 1
            cells[grid_cell(op, f.a, f.b, f.answer)] = {
                'id': f.id, 'label': grid_label(op, f.a, f.b, f.answer),
                'status': status,
                'selected': f.id in selected,
                'title': f'{f} · {STATUS_LABELS[status]}',
            }
        rows = []
        for r in spec['rows']:
            row = [cells.get((r, c)) for c in spec['cols']]
            if any(row):
                rows.append({'head': r, 'cells': row})
        grids.append({
            'op': op,
            'title': f'{OP_NAMES[op]} ({OP_SYMBOLS[op]})',
            'symbol': OP_SYMBOLS[op],
            'cols': spec['cols'],
            'rows': rows,
            'note': spec['note'],
        })
    total = sum(counts.values())
    recent = (Attempt.objects
              .filter(student=student, correct=True, fact__operation__in=ops)
              .order_by('-created_at')[:50]
              .aggregate(avg=Avg('response_ms')))
    return {
        'grids': grids,
        'counts': counts,
        'legend': [{'key': k, 'label': STATUS_LABELS[k], 'count': counts[k]}
                   for k in STATUS_ORDER],
        'batches': [batches[s] for s in sorted(batches) if batches[s]['total']],
        'status_labels': STATUS_LABELS,
        'total_facts': total,
        'mastered_count': counts['mastered'],
        'streak': _streak(student),
        'avg_recent_s': round(recent['avg'] / 1000, 1) if recent['avg'] else None,
        'can_select': can_select,
        'selected_count': len(selected),
        'working_on': _working_on(student),
    }
