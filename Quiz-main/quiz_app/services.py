import logging
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from .models import (
    User, Task, TaskOption, UserProgress, LevelAttempt, Achievement, UserAchievement
)

logger = logging.getLogger('quiz_app')


# ---------------------------------------------------------------------------
# Вспомогательные функции для math_path
# ---------------------------------------------------------------------------

def parse_operation(op_str: str):
    """
    Парсит строку операции вида '+5', '-3', '*2', '/4'.
    Возвращает callable или None при ошибке.
    """
    op_str = op_str.strip()
    if not op_str:
        return None
    operator = op_str[0]
    try:
        value = int(op_str[1:])
    except (ValueError, IndexError):
        return None

    ops = {
        '+': lambda x, v=value: x + v,
        '-': lambda x, v=value: x - v,
        '*': lambda x, v=value: x * v,
        '/': lambda x, v=value: x // v if v != 0 else x,
    }
    return ops.get(operator)


def validate_math_path_solution(task: Task, solution_path: list) -> dict:
    """
    Проверяет решение задания типа math_path.

    Args:
        task: объект Task
        solution_path: список целых чисел — последовательность значений

    Returns:
        dict с ключами: is_correct, errors_count, message
    """
    if not solution_path:
        return {'is_correct': False, 'errors_count': 1, 'message': 'Пустой путь решения.'}

    op1 = parse_operation(task.operation_1)
    op2 = parse_operation(task.operation_2)

    if op1 is None or op2 is None:
        return {'is_correct': False, 'errors_count': 0,
                'message': 'Некорректные операции в задании.'}

    # Первый элемент пути должен быть start_value
    if solution_path[0] != task.start_value:
        return {'is_correct': False, 'errors_count': 1,
                'message': f'Путь должен начинаться с {task.start_value}.'}

    errors = 0
    for i in range(1, len(solution_path)):
        prev = solution_path[i - 1]
        curr = solution_path[i]
        valid_next = {op1(prev), op2(prev)}
        if curr not in valid_next:
            errors += 1

    is_correct = (solution_path[-1] == task.target_value) and errors == 0
    message = 'Правильно!' if is_correct else (
        f'Достигнутое значение: {solution_path[-1]}, ожидается: {task.target_value}.'
        if errors == 0 else f'Обнаружено {errors} некорректных шагов.'
    )
    return {'is_correct': is_correct, 'errors_count': errors, 'message': message}


def validate_test_solution(task: Task, selected_option_ids: list) -> dict:
    """Проверяет ответы для тестовых заданий (один/несколько вариантов)."""
    correct_ids = set(
        task.options.filter(is_correct=True).values_list('id', flat=True)
    )
    selected_ids = set(selected_option_ids)

    is_correct = correct_ids == selected_ids
    errors = len(correct_ids.symmetric_difference(selected_ids))
    return {
        'is_correct': is_correct,
        'errors_count': errors,
        'correct_ids': list(correct_ids),
        'message': 'Правильно!' if is_correct else 'Неправильный ответ.'
    }


def validate_text_answer(task: Task, text_answer: str) -> dict:
    """Проверяет текстовый ответ (без учёта регистра и пробелов)."""
    correct = task.correct_answer_text.strip().lower()
    given   = text_answer.strip().lower()
    is_correct = correct == given
    return {
        'is_correct': is_correct,
        'errors_count': 0 if is_correct else 1,
        'message': 'Правильно!' if is_correct else f'Правильный ответ: {task.correct_answer_text}'
    }


# ---------------------------------------------------------------------------
# Расчёт XP
# ---------------------------------------------------------------------------

def calculate_xp(task: Task, is_correct: bool, errors_made: int,
                 time_spent: int, steps_taken: int = 0) -> int:
    """
    Рассчитывает XP за попытку.
    Учитывает: правильность, сложность, бонус за скорость, штраф за ошибки.
    """
    if not is_correct:
        return 0

    cfg = settings.GAMIFICATION
    base_xp = task.get_xp_reward_with_difficulty()

    # Штраф за ошибки: -10% за каждую ошибку, минимум 50% от базы
    error_penalty = max(0.5, 1.0 - errors_made * 0.1)
    xp = int(base_xp * error_penalty)

    # Бонус за скорость
    if time_spent > 0 and time_spent < cfg['XP_SPEED_BONUS_SECONDS']:
        xp += cfg['XP_SPEED_BONUS_AMOUNT']

    # Бонус за оптимальное решение (для math_path)
    if task.optimal_steps and steps_taken > 0:
        if steps_taken <= task.optimal_steps:
            xp = int(xp * 1.2)  # +20% за оптимальный путь

    return max(0, xp)


# ---------------------------------------------------------------------------
# Основной сервис обработки попытки
# ---------------------------------------------------------------------------

@transaction.atomic
def process_attempt(user: User, task: Task, data: dict) -> dict:
    """
    Основная функция обработки попытки прохождения задания.
    Сохраняет LevelAttempt, обновляет UserProgress, начисляет XP,
    проверяет и выдаёт ачивки.

    Args:
        user: текущий пользователь
        task: задание
        data: валидированные данные из SubmitAttemptSerializer

    Returns:
        dict с результатом
    """
    task_type = task.task_type

    # 1. Проверяем ответ в зависимости от типа задания
    if task_type == Task.TaskType.MATH_PATH:
        solution_path = data.get('solution_path', [])
        check = validate_math_path_solution(task, solution_path)
        steps_taken = len(solution_path) - 1 if solution_path else 0
    elif task_type in (Task.TaskType.SINGLE_TEST, Task.TaskType.MULTI_TEST):
        check = validate_test_solution(task, data.get('selected_option_ids', []))
        steps_taken = 0
        solution_path = None
    elif task_type == Task.TaskType.TEXT_INPUT:
        check = validate_text_answer(task, data.get('text_answer', ''))
        steps_taken = 0
        solution_path = None
    else:
        check = {'is_correct': False, 'errors_count': 0, 'message': 'Тип задания не поддерживается.'}
        steps_taken = 0
        solution_path = None

    is_success   = check['is_correct']
    errors_made  = check.get('errors_count', data.get('errors_made', 0))
    time_spent   = data.get('time_spent', 0)

    # 2. Рассчитываем XP
    xp_earned = calculate_xp(task, is_success, errors_made, time_spent, steps_taken)

    # 3. Сохраняем попытку
    attempt = LevelAttempt.objects.create(
        user          = user,
        task          = task,
        is_success    = is_success,
        errors_made   = errors_made,
        steps_taken   = steps_taken,
        xp_earned     = xp_earned,
        time_spent    = time_spent,
        solution_path = data.get('solution_path'),
        finished_at   = timezone.now(),
    )

    # 4. Обновляем прогресс пользователя по теме
    progress, _ = UserProgress.objects.get_or_create(
        user=user, topic=task.topic,
        defaults={'tasks_total': task.topic.tasks.filter(is_active=True).count()}
    )
    progress.tasks_total = task.topic.tasks.filter(is_active=True).count()
    progress.total_errors += errors_made

    if is_success:
        # Считаем уникальные успешные задания
        completed_tasks = LevelAttempt.objects.filter(
            user=user, task__topic=task.topic, is_success=True
        ).values('task').distinct().count()
        progress.tasks_completed = completed_tasks

        if progress.tasks_completed >= progress.tasks_total:
            progress.is_completed = True
            if not progress.completed_at:
                progress.completed_at = timezone.now()

        progress.total_xp_earned += xp_earned
        if xp_earned > progress.best_score:
            progress.best_score = xp_earned

    progress.save()

    # 5. Начисляем XP пользователю
    if xp_earned > 0:
        user.total_xp += xp_earned
        user.last_activity = timezone.now().date()
        user.save(update_fields=['total_xp', 'last_activity'])
        user.recalculate_level()

    # 6. Проверяем и выдаём ачивки
    new_achievements = check_and_award_achievements(user, attempt)

    logger.info(
        f'Attempt: user={user.id} task={task.id} success={is_success} '
        f'xp={xp_earned} errors={errors_made}'
    )

    return {
        'is_success':       is_success,
        'message':          check['message'],
        'xp_earned':        xp_earned,
        'errors_made':      errors_made,
        'new_achievements': [str(a.achievement) for a in new_achievements],
        'user_total_xp':    user.total_xp,
        'user_level':       user.game_level,
        'correct_answer':   check.get('correct_ids') or task.correct_answer_text,
        'attempt_id':       attempt.id,
    }


# ---------------------------------------------------------------------------
# Система ачивок
# ---------------------------------------------------------------------------

def check_and_award_achievements(user: User, attempt: LevelAttempt) -> list:
    """
    Проверяет все ачивки и выдаёт те, которые пользователь ещё не получил.
    Возвращает список новых UserAchievement.
    """
    earned_ids = set(user.achievements.values_list('achievement_id', flat=True))
    all_achievements = Achievement.objects.exclude(id__in=earned_ids)
    new_awards = []

    for ach in all_achievements:
        if _is_achievement_earned(user, attempt, ach):
            ua = UserAchievement.objects.create(user=user, achievement=ach)
            # Начисляем бонус XP за ачивку
            user.total_xp += ach.xp_reward
            new_awards.append(ua)

    if new_awards:
        user.save(update_fields=['total_xp'])
        user.recalculate_level()

    return new_awards


def _is_achievement_earned(user: User, attempt: LevelAttempt, ach: Achievement) -> bool:
    """Проверяет выполнение условия конкретной ачивки."""
    from .models import LevelAttempt as LA, UserProgress

    if ach.ach_type == Achievement.AchievementType.STREAK:
        return user.streak_days >= ach.condition_value

    elif ach.ach_type == Achievement.AchievementType.SCORE:
        return user.total_xp >= ach.condition_value

    elif ach.ach_type == Achievement.AchievementType.COMPLETION:
        completed = UserProgress.objects.filter(
            user=user, is_completed=True
        ).count()
        return completed >= ach.condition_value

    elif ach.ach_type == Achievement.AchievementType.ACCURACY:
        # N заданий подряд без ошибок
        recent = LA.objects.filter(user=user).order_by('-started_at')[:ach.condition_value]
        if recent.count() < ach.condition_value:
            return False
        return all(a.errors_made == 0 and a.is_success for a in recent)

    elif ach.ach_type == Achievement.AchievementType.SPEED:
        return (attempt.time_spent > 0 and
                attempt.time_spent <= ach.condition_value and
                attempt.is_success)

    return False