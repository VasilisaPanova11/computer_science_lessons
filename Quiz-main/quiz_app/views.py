"""
Views для ИС «Геймификация Информатика».
Используют Django-шаблоны и стандартную сессионную аутентификацию.
"""

import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum, Avg, Count
from django.utils import timezone

from .models import (
    User, ClassGroup, Subject, Topic, Task,
    UserProgress, LevelAttempt, Achievement, UserAchievement
)
from .services import process_attempt

logger = logging.getLogger('quiz_app')


# ---------------------------------------------------------------------------
# Вспомогательные декораторы
# ---------------------------------------------------------------------------

def role_required(*roles):
    """Декоратор: разрешить доступ только указанным ролям."""
    def decorator(view_func):
        @login_required(login_url='login')
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, 'У вас нет доступа к этой странице.')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Аутентификация
# ---------------------------------------------------------------------------

def login_view(request):
    """Страница входа. GET — форма, POST — обработка."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user     = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', '')
            return redirect(next_url if next_url else 'dashboard')
        else:
            messages.error(request, 'Неверный email или пароль.')

    return render(request, 'quiz_app/login.html')


def register_view(request):
    """Страница регистрации."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email      = request.POST.get('email', '').strip()
        username   = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        password   = request.POST.get('password', '')
        password2  = request.POST.get('password2', '')

        errors = []
        if not email:             errors.append('Email обязателен.')
        if not username:          errors.append('Логин обязателен.')
        if not first_name:        errors.append('Имя обязательно.')
        if not last_name:         errors.append('Фамилия обязательна.')
        if password != password2: errors.append('Пароли не совпадают.')
        if len(password) < 8:     errors.append('Пароль — минимум 8 символов.')
        if User.objects.filter(email=email).exists():
            errors.append('Пользователь с таким email уже существует.')
        if User.objects.filter(username=username).exists():
            errors.append('Такой логин уже занят.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'quiz_app/login.html', {
                'tab': 'register',
                'form_data': request.POST,
            })

        user = User.objects.create_user(
            email=email, username=username,
            first_name=first_name, last_name=last_name,
            password=password,
        )
        login(request, user)
        messages.success(request, f'Добро пожаловать, {first_name}! 🎉')
        return redirect('dashboard')

    return render(request, 'quiz_app/login.html', {'tab': 'register'})


def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect('login')


def password_reset_view(request):
    """Запрос на сброс пароля через email."""
    if request.method == 'POST':
        from django.core.mail import send_mail
        from django.conf import settings

        email = request.POST.get('email', '').strip()
        try:
            user  = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            reset_url = request.build_absolute_uri(
                f'/reset-password/{user.pk}/{token}/'
            )
            send_mail(
                subject='Восстановление пароля — ИС Геймификация',
                message=f'Перейдите по ссылке для сброса пароля:\n{reset_url}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
        except User.DoesNotExist:
            pass

        messages.success(request, 'Если email зарегистрирован — письмо отправлено.')
        return redirect('login')

    return render(request, 'quiz_app/password_reset.html')


# ---------------------------------------------------------------------------
# Дашборд
# ---------------------------------------------------------------------------

@login_required(login_url='login')
def dashboard_view(request):
    """Главный дашборд. Содержимое зависит от роли пользователя."""
    user = request.user

    if user.role == User.Role.STUDENT:
        return _student_dashboard(request, user)
    elif user.role == User.Role.TEACHER:
        return _teacher_dashboard(request, user)
    else:
        return _admin_dashboard(request, user)


def _student_dashboard(request, user):
    progress     = UserProgress.objects.filter(user=user).select_related('topic__subject')
    recent       = LevelAttempt.objects.filter(user=user).order_by('-started_at').select_related('task')[:10]
    earned       = UserAchievement.objects.filter(user=user).select_related('achievement')
    all_achs     = Achievement.objects.filter(is_hidden=False)
    earned_ids   = set(earned.values_list('achievement_id', flat=True))
    total_done   = LevelAttempt.objects.filter(user=user, is_success=True).count()
    total_errors = LevelAttempt.objects.filter(user=user).aggregate(s=Sum('errors_made'))['s'] or 0

    rank = None
    if user.class_group:
        rank = User.objects.filter(
            class_group=user.class_group, total_xp__gt=user.total_xp
        ).count() + 1

    return render(request, 'quiz_app/dashboard.html', {
        'progress':     progress,
        'recent':       recent,
        'all_achs':     all_achs,
        'earned_ids':   earned_ids,
        'rank':         rank,
        'total_done':   total_done,
        'total_errors': total_errors,
    })


def _teacher_dashboard(request, user):
    classes      = ClassGroup.objects.filter(teacher=user).prefetch_related('students')
    classes_data = []
    for cls in classes:
        students = cls.students.all()
        agg      = students.aggregate(avg_xp=Avg('total_xp'), avg_level=Avg('game_level'))
        problem_topics = (
            UserProgress.objects
            .filter(user__class_group=cls)
            .values('topic__title')
            .annotate(errors=Sum('total_errors'))
            .order_by('-errors')[:5]
        )
        classes_data.append({
            'class_group':    cls,
            'students':       students.order_by('-total_xp'),
            'students_count': students.count(),
            'avg_xp':         round(agg['avg_xp'] or 0, 1),
            'avg_level':      round(agg['avg_level'] or 0, 1),
            'problem_topics': list(problem_topics),
        })
    return render(request, 'quiz_app/teacher_dashboard.html', {
        'classes_data': classes_data,
    })


def _admin_dashboard(request, user):
    return render(request, 'quiz_app/admin_dashboard.html', {
        'total_users':    User.objects.count(),
        'total_students': User.objects.filter(role=User.Role.STUDENT).count(),
        'total_teachers': User.objects.filter(role=User.Role.TEACHER).count(),
        'total_tasks':    Task.objects.filter(is_active=True).count(),
        'total_attempts': LevelAttempt.objects.count(),
    })


# ---------------------------------------------------------------------------
# Разделы и темы
# ---------------------------------------------------------------------------

@login_required(login_url='login')
def subjects_view(request):
    """Список всех разделов с темами."""
    subjects = Subject.objects.prefetch_related('topics').order_by('order')

    user_progress = {}
    if request.user.role == User.Role.STUDENT:
        for prog in UserProgress.objects.filter(user=request.user).select_related('topic'):
            user_progress[prog.topic_id] = prog

    return render(request, 'quiz_app/subjects.html', {
        'subjects':      subjects,
        'user_progress': user_progress,
    })


@login_required(login_url='login')
def topic_detail_view(request, topic_id):
    """Страница темы: теория + список заданий."""
    topic  = get_object_or_404(Topic, pk=topic_id)
    tasks  = topic.tasks.filter(is_active=True).order_by('order')

    progress           = None
    completed_task_ids = set()
    if request.user.role == User.Role.STUDENT:
        progress = UserProgress.objects.filter(user=request.user, topic=topic).first()
        completed_task_ids = set(
            LevelAttempt.objects.filter(
                user=request.user, task__topic=topic, is_success=True
            ).values_list('task_id', flat=True).distinct()
        )

    return render(request, 'quiz_app/topic_detail.html', {
        'topic':              topic,
        'tasks':              tasks,
        'progress':           progress,
        'completed_task_ids': completed_task_ids,
    })


# ---------------------------------------------------------------------------
# Игровой экран
# ---------------------------------------------------------------------------

@login_required(login_url='login')
def game_view(request, task_id):
    """Игровой экран для конкретного задания."""
    task = get_object_or_404(Task, pk=task_id, is_active=True)
    
    # Базовый QuerySet для всех попыток пользователя по этому заданию
    attempts_qs = LevelAttempt.objects.filter(user=request.user, task=task)
    
    # Лучшая успешная попытка (по шагам)
    best_attempt = attempts_qs.filter(is_success=True).order_by('steps_taken').first()
    
    # Последние 5 попыток для отображения
    recent_attempts = attempts_qs.order_by('-started_at')[:5]
    
    return render(request, 'quiz_app/game.html', {
        'task': task,
        'attempts': recent_attempts,
        'best_attempt': best_attempt,
        'task_json': json.dumps({
            'id': task.id,
            'title': task.title,
            'description': task.description or '',
            'task_type': task.task_type,
            'start_value': task.start_value,
            'target_value': task.target_value,
            'operation_1': task.operation_1,
            'operation_2': task.operation_2,
            'max_steps': task.max_steps,
            'optimal_steps': task.optimal_steps,
            'difficulty': task.difficulty,
            'xp_reward': task.xp_reward * task.difficulty,
        }),
    })


@login_required(login_url='login')
@require_POST
def submit_answer_view(request, task_id):
    """
    AJAX-эндпоинт: принимает ответ, возвращает JSON с результатом.
    Вызывается со страницы game.html через fetch().
    """
    task = get_object_or_404(Task, pk=task_id, is_active=True)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный JSON.'}, status=400)

    result = process_attempt(request.user, task, data)
    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Профиль
# ---------------------------------------------------------------------------

@login_required(login_url='login')
def profile_view(request):
    """Просмотр и редактирование профиля."""
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            user.first_name = request.POST.get('first_name', user.first_name).strip()
            user.last_name  = request.POST.get('last_name',  user.last_name).strip()
            user.patronymic = request.POST.get('patronymic', user.patronymic).strip()
            if 'avatar' in request.FILES:
                user.avatar = request.FILES['avatar']
            user.save()
            messages.success(request, 'Профиль обновлён.')

        elif action == 'change_password':
            old_pw  = request.POST.get('old_password', '')
            new_pw  = request.POST.get('new_password', '')
            new_pw2 = request.POST.get('new_password2', '')
            if not user.check_password(old_pw):
                messages.error(request, 'Неверный текущий пароль.')
            elif new_pw != new_pw2:
                messages.error(request, 'Новые пароли не совпадают.')
            elif len(new_pw) < 8:
                messages.error(request, 'Пароль — минимум 8 символов.')
            else:
                user.set_password(new_pw)
                user.save()
                login(request, user)
                messages.success(request, 'Пароль успешно изменён.')

        return redirect('profile')

    achievements = UserAchievement.objects.filter(user=user).select_related('achievement')
    recent       = LevelAttempt.objects.filter(user=user).order_by('-started_at')[:20]

    return render(request, 'quiz_app/profile.html', {
        'achievements': achievements,
        'recent':       recent,
    })


# ---------------------------------------------------------------------------
# Таблица лидеров
# ---------------------------------------------------------------------------

@login_required(login_url='login')
def leaderboard_view(request):
    """Таблица лидеров по классу или общая."""
    user     = request.user
    class_id = request.GET.get('class')

    if class_id:
        class_group = get_object_or_404(ClassGroup, pk=class_id)
        students    = User.objects.filter(
            class_group=class_group, role=User.Role.STUDENT, is_active=True
        ).order_by('-total_xp')
    elif user.class_group:
        class_group = user.class_group
        students    = User.objects.filter(
            class_group=user.class_group, role=User.Role.STUDENT, is_active=True
        ).order_by('-total_xp')
    else:
        class_group = None
        students    = User.objects.filter(
            role=User.Role.STUDENT, is_active=True
        ).order_by('-total_xp')[:50]

    ranked = [
        {'rank': i + 1, 'student': s, 'is_me': s.id == user.id}
        for i, s in enumerate(students)
    ]

    return render(request, 'quiz_app/leaderboard.html', {
        'ranked':      ranked,
        'class_group': class_group,
        'all_classes': ClassGroup.objects.filter(is_active=True),
    })


# ---------------------------------------------------------------------------
# Достижения
# ---------------------------------------------------------------------------

@login_required(login_url='login')
def achievements_view(request):
    """Страница всех достижений."""
    all_achs  = Achievement.objects.filter(is_hidden=False)
    earned_qs = UserAchievement.objects.filter(user=request.user).select_related('achievement')
    earned_at = {ua.achievement_id: ua.earned_at for ua in earned_qs}
    earned_ids= set(earned_at.keys())

    achs_data = [
        {'ach': a, 'earned': a.id in earned_ids, 'earned_at': earned_at.get(a.id)}
        for a in all_achs
    ]

    return render(request, 'quiz_app/achievements.html', {
        'achs_data':    achs_data,
        'earned_count': len(earned_ids),
        'total_count':  all_achs.count(),
    })


# ---------------------------------------------------------------------------
# Управление классами (учитель)
# ---------------------------------------------------------------------------

@role_required(User.Role.TEACHER, User.Role.ADMIN)
def classes_view(request):
    """Список классов учителя."""
    if request.user.role == User.Role.ADMIN:
        classes = ClassGroup.objects.all().prefetch_related('students')
    else:
        classes = ClassGroup.objects.filter(teacher=request.user).prefetch_related('students')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            ClassGroup.objects.create(
                name=name,
                description=request.POST.get('description', ''),
                teacher=request.user if request.user.role == User.Role.TEACHER else None,
            )
            messages.success(request, f'Класс «{name}» создан.')
        return redirect('classes')

    return render(request, 'quiz_app/classes.html', {'classes': classes})


@role_required(User.Role.TEACHER, User.Role.ADMIN)
def class_detail_view(request, class_id):
    """Детальная страница класса: ученики, прогресс, рейтинг."""
    class_group = get_object_or_404(ClassGroup, pk=class_id)

    if request.user.role == User.Role.TEACHER and class_group.teacher != request.user:
        messages.error(request, 'Это не ваш класс.')
        return redirect('classes')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_student':
            username = request.POST.get('username', '').strip()
            try:
                student             = User.objects.get(username=username, role=User.Role.STUDENT)
                student.class_group = class_group
                student.save(update_fields=['class_group'])
                messages.success(request, f'{student.get_full_name()} добавлен в класс.')
            except User.DoesNotExist:
                messages.error(request, 'Ученик с таким логином не найден.')

        elif action == 'remove_student':
            student_id = request.POST.get('student_id')
            try:
                student             = User.objects.get(pk=student_id, class_group=class_group)
                student.class_group = None
                student.save(update_fields=['class_group'])
                messages.success(request, f'{student.get_full_name()} удалён из класса.')
            except User.DoesNotExist:
                messages.error(request, 'Ученик не найден.')

        return redirect('class_detail', class_id=class_id)

    students = class_group.students.order_by('-total_xp')
    problem_topics = (
        UserProgress.objects
        .filter(user__class_group=class_group)
        .values('topic__title')
        .annotate(errors=Sum('total_errors'), attempts=Count('id'))
        .order_by('-errors')[:8]
    )

    return render(request, 'quiz_app/class_detail.html', {
        'class_group':    class_group,
        'students':       students,
        'problem_topics': problem_topics,
    })


# ---------------------------------------------------------------------------
# Управление заданиями (учитель)
# ---------------------------------------------------------------------------

@role_required(User.Role.TEACHER, User.Role.ADMIN)
def task_create_view(request, topic_id):
    """Создание нового задания в теме."""
    topic = get_object_or_404(Topic, pk=topic_id)

    if request.method == 'POST':
        task = Task.objects.create(
            topic        = topic,
            title        = request.POST.get('title', '').strip(),
            description  = request.POST.get('description', '').strip(),
            task_type    = request.POST.get('task_type', Task.TaskType.MATH_PATH),
            difficulty   = int(request.POST.get('difficulty', 2)),
            xp_reward    = int(request.POST.get('xp_reward', 10)),
            order        = int(request.POST.get('order', 0)),
            start_value  = request.POST.get('start_value') or None,
            target_value = request.POST.get('target_value') or None,
            operation_1  = request.POST.get('operation_1', '').strip(),
            operation_2  = request.POST.get('operation_2', '').strip(),
            max_steps    = int(request.POST.get('max_steps', 10)),
            optimal_steps= request.POST.get('optimal_steps') or None,
            correct_answer_text = request.POST.get('correct_answer_text', '').strip(),
            created_by   = request.user,
            is_active    = True,
        )
        messages.success(request, f'Задание «{task.title}» создано.')
        return redirect('topic_detail', topic_id=topic.id)

    return render(request, 'quiz_app/task_form.html', {
        'topic':      topic,
        'task_types': Task.TaskType.choices,
        'action':     'create',
    })