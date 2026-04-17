from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import math


# ---------------------------------------------------------------------------
# Менеджер пользователей
# ---------------------------------------------------------------------------

class UserManager(BaseUserManager):
    """Кастомный менеджер для модели User."""

    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        return self.create_user(email, username, password, **extra_fields)


# ---------------------------------------------------------------------------
# Пользователь
# ---------------------------------------------------------------------------

class User(AbstractBaseUser, PermissionsMixin):
    """
    Кастомная модель пользователя.
    Поддерживает три роли: Ученик, Учитель, Администратор.
    """

    class Role(models.TextChoices):
        STUDENT = 'student', 'Ученик'
        TEACHER = 'teacher', 'Учитель'
        ADMIN   = 'admin',   'Администратор'

    # Основные поля
    email        = models.EmailField(unique=True, verbose_name='Email')
    username     = models.CharField(max_length=50, unique=True, verbose_name='Логин')
    first_name   = models.CharField(max_length=50, verbose_name='Имя')
    last_name    = models.CharField(max_length=50, verbose_name='Фамилия')
    patronymic   = models.CharField(max_length=50, blank=True, verbose_name='Отчество')
    role         = models.CharField(max_length=10, choices=Role.choices,
                                    default=Role.STUDENT, verbose_name='Роль')
    avatar       = models.ImageField(upload_to='avatars/', null=True, blank=True,
                                     verbose_name='Аватар')

    # Служебные поля
    is_active    = models.BooleanField(default=True)
    is_staff     = models.BooleanField(default=False)
    date_joined  = models.DateTimeField(default=timezone.now, verbose_name='Дата регистрации')

    # Связь с классом (для учеников)
    class_group  = models.ForeignKey(
        'ClassGroup', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='students',
        verbose_name='Класс'
    )

    # Геймификационные поля
    total_xp     = models.PositiveIntegerField(default=0, verbose_name='Опыт (XP)')
    game_level   = models.PositiveSmallIntegerField(default=1, verbose_name='Уровень')
    streak_days  = models.PositiveIntegerField(default=0, verbose_name='Дней подряд')
    last_activity= models.DateField(null=True, blank=True, verbose_name='Последняя активность')

    objects = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name        = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering            = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.last_name} {self.first_name} {self.username} ({self.get_role_display()})'

    def get_full_name(self):
        return f'{self.last_name} {self.first_name} {self.patronymic}'.strip()

    def recalculate_level(self):
        """Пересчитывает игровой уровень на основе суммарного XP."""
        xp_per_level = 100
        self.game_level = max(1, int(math.sqrt(self.total_xp / xp_per_level)) + 1)
        self.save(update_fields=['game_level'])

    @property
    def xp_to_next_level(self):
        """XP до следующего уровня."""
        xp_per_level = 100
        next_level_xp = ((self.game_level) ** 2) * xp_per_level
        return max(0, next_level_xp - self.total_xp)

    @property
    def xp_progress_percent(self):
        """Прогресс XP до следующего уровня в процентах."""
        xp_per_level = 100
        current_level_xp = ((self.game_level - 1) ** 2) * xp_per_level
        next_level_xp    = ((self.game_level) ** 2) * xp_per_level
        level_range      = next_level_xp - current_level_xp
        if level_range == 0:
            return 100
        return int(((self.total_xp - current_level_xp) / level_range) * 100)

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN



# ---------------------------------------------------------------------------
# Класс (группа учеников)
# ---------------------------------------------------------------------------

class ClassGroup(models.Model):
    """Учебный класс / группа. Создаётся учителем."""

    name        = models.CharField(max_length=20, verbose_name='Название класса')
    description = models.TextField(blank=True, verbose_name='Описание')
    teacher     = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='taught_classes',
        limit_choices_to={'role': User.Role.TEACHER},
        verbose_name='Учитель'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    is_active   = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name        = 'Класс'
        verbose_name_plural = 'Классы'
        ordering            = ['name']

    def __str__(self):
        return f'{self.name} (учитель: {self.teacher})'


# ---------------------------------------------------------------------------
# Иерархия учебного контента: Раздел → Тема → Задание
# ---------------------------------------------------------------------------

class Subject(models.Model):
    """Раздел (верхний уровень иерархии контента)."""

    title       = models.CharField(max_length=100, verbose_name='Название раздела')
    description = models.TextField(blank=True, verbose_name='Описание')
    order       = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')
    icon        = models.CharField(max_length=50, blank=True, verbose_name='Иконка (CSS-класс)')

    class Meta:
        verbose_name        = 'Раздел'
        verbose_name_plural = 'Разделы'
        ordering            = ['order', 'title']

    def __str__(self):
        return self.title


class Topic(models.Model):
    """Тема внутри раздела."""

    subject     = models.ForeignKey(Subject, on_delete=models.CASCADE,
                                    related_name='topics', verbose_name='Раздел')
    title       = models.CharField(max_length=150, verbose_name='Название темы')
    description = models.TextField(blank=True, verbose_name='Описание')
    theory_text = models.TextField(blank=True, verbose_name='Теоретический материал')
    order       = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')
    created_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        limit_choices_to={'role__in': [User.Role.TEACHER, User.Role.ADMIN]},
        verbose_name='Создал'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Тема'
        verbose_name_plural = 'Темы'
        ordering            = ['subject', 'order']

    def __str__(self):
        return f'{self.subject.title} → {self.title}'


# ---------------------------------------------------------------------------
# Задание (уровень игры)
# ---------------------------------------------------------------------------

class Task(models.Model):
    """
    Игровой уровень-задание.
    Тип 'math_path': нужно перейти от start_value к target_value,
    используя только operation_1 и operation_2.
    """

    class TaskType(models.TextChoices):
        MATH_PATH   = 'math_path',  'Математический путь'   # Основной игровой тип
        SINGLE_TEST = 'single',     'Тест (один ответ)'
        MULTI_TEST  = 'multi',      'Тест (несколько ответов)'
        TEXT_INPUT  = 'text_input', 'Развёрнутый ответ'
        MATCHING    = 'matching',   'Соответствие'

    class Difficulty(models.IntegerChoices):
        EASY   = 1, 'Лёгкий'
        MEDIUM = 2, 'Средний'
        HARD   = 3, 'Сложный'

    topic       = models.ForeignKey(Topic, on_delete=models.CASCADE,
                                    related_name='tasks', verbose_name='Тема')
    title       = models.CharField(max_length=200, verbose_name='Название задания')
    description = models.TextField(blank=True, verbose_name='Описание / условие')
    task_type   = models.CharField(max_length=15, choices=TaskType.choices,
                                   default=TaskType.MATH_PATH, verbose_name='Тип задания')
    difficulty  = models.IntegerField(choices=Difficulty.choices,
                                      default=Difficulty.MEDIUM, verbose_name='Сложность')
    xp_reward   = models.PositiveIntegerField(default=10, verbose_name='Награда XP')
    order       = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')
    is_active   = models.BooleanField(default=True, verbose_name='Активно')
    created_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        limit_choices_to={'role__in': [User.Role.TEACHER, User.Role.ADMIN]},
        verbose_name='Создал'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    # ---- Поля для типа MATH_PATH ----
    start_value   = models.IntegerField(null=True, blank=True, verbose_name='Начальное значение')
    target_value  = models.IntegerField(null=True, blank=True, verbose_name='Целевое значение')
    operation_1   = models.CharField(max_length=20, blank=True,
                                     verbose_name='Операция 1 (напр. "+5" или "*2")')
    operation_2   = models.CharField(max_length=20, blank=True,
                                     verbose_name='Операция 2 (напр. "-3" или "/2")')
    max_steps     = models.PositiveSmallIntegerField(default=10,
                                                     verbose_name='Максимум шагов')
    optimal_steps = models.PositiveSmallIntegerField(null=True, blank=True,
                                                     verbose_name='Оптимальное кол-во шагов')

    # ---- Поля для тестовых типов ----
    # Варианты ответов хранятся в связанной модели TaskOption

    # ---- Поля для text_input ----
    correct_answer_text = models.CharField(max_length=500, blank=True,
                                           verbose_name='Правильный ответ (текст)')

    class Meta:
        verbose_name        = 'Задание'
        verbose_name_plural = 'Задания'
        ordering            = ['topic', 'order']

    def __str__(self):
        return f'[{self.get_task_type_display()}] {self.title}'

    def get_xp_reward_with_difficulty(self):
        """XP с учётом сложности."""
        return self.xp_reward * self.difficulty


class TaskOption(models.Model):
    """Вариант ответа для тестовых заданий и заданий на соответствие."""

    task        = models.ForeignKey(Task, on_delete=models.CASCADE,
                                    related_name='options', verbose_name='Задание')
    text        = models.CharField(max_length=500, verbose_name='Текст варианта')
    is_correct  = models.BooleanField(default=False, verbose_name='Правильный')
    # Для заданий на соответствие
    match_key   = models.CharField(max_length=200, blank=True,
                                   verbose_name='Ключ соответствия')
    match_value = models.CharField(max_length=200, blank=True,
                                   verbose_name='Значение соответствия')
    order       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering            = ['order']

    def __str__(self):
        return f'{self.task.title[:30]} | {self.text[:30]}'


# ---------------------------------------------------------------------------
# Прогресс пользователя
# ---------------------------------------------------------------------------

class UserProgress(models.Model):
    """
    Прогресс пользователя по теме.
    Агрегированная статистика для дашборда.
    """

    user            = models.ForeignKey(User, on_delete=models.CASCADE,
                                        related_name='progress', verbose_name='Пользователь')
    topic           = models.ForeignKey(Topic, on_delete=models.CASCADE,
                                        related_name='user_progress', verbose_name='Тема')
    tasks_completed = models.PositiveIntegerField(default=0, verbose_name='Заданий пройдено')
    tasks_total     = models.PositiveIntegerField(default=0, verbose_name='Всего заданий')
    total_errors    = models.PositiveIntegerField(default=0, verbose_name='Ошибок всего')
    best_score      = models.PositiveIntegerField(default=0, verbose_name='Лучший результат')
    total_xp_earned = models.PositiveIntegerField(default=0, verbose_name='XP за тему')
    is_completed    = models.BooleanField(default=False, verbose_name='Тема завершена')
    started_at      = models.DateTimeField(auto_now_add=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Прогресс пользователя'
        verbose_name_plural = 'Прогресс пользователей'
        unique_together     = ('user', 'topic')
        ordering            = ['-updated_at']

    def __str__(self):
        return f'{self.user} | {self.topic.title} | {self.tasks_completed}/{self.tasks_total}'

    @property
    def completion_percent(self):
        if self.tasks_total == 0:
            return 0
        return int((self.tasks_completed / self.tasks_total) * 100)


class LevelAttempt(models.Model):
    """
    Попытка прохождения конкретного задания.
    Хранит детальную историю каждого прохождения.
    """

    user        = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='attempts', verbose_name='Пользователь')
    task        = models.ForeignKey(Task, on_delete=models.CASCADE,
                                    related_name='attempts', verbose_name='Задание')
    is_success  = models.BooleanField(default=False, verbose_name='Успешно')
    errors_made = models.PositiveSmallIntegerField(default=0, verbose_name='Ошибок сделано')
    steps_taken = models.PositiveSmallIntegerField(default=0, verbose_name='Шагов сделано')
    xp_earned   = models.PositiveIntegerField(default=0, verbose_name='XP получено')
    time_spent  = models.PositiveIntegerField(default=0, verbose_name='Время (сек)')
    # Для math_path: сохраняем путь решения как JSON-строку
    solution_path = models.JSONField(null=True, blank=True, verbose_name='Путь решения')
    started_at  = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Попытка прохождения'
        verbose_name_plural = 'Попытки прохождений'
        ordering            = ['-started_at']

    def __str__(self):
        status = '✓' if self.is_success else '✗'
        return f'{status} {self.user} | {self.task.title} | ошибок: {self.errors_made}'


# ---------------------------------------------------------------------------
# Достижения (Ачивки)
# ---------------------------------------------------------------------------

class Achievement(models.Model):
    """Достижение / ачивка."""

    class AchievementType(models.TextChoices):
        STREAK       = 'streak',    'Серия дней'
        SCORE        = 'score',     'Результат'
        COMPLETION   = 'completion','Завершение'
        SPEED        = 'speed',     'Скорость'
        ACCURACY     = 'accuracy',  'Точность'
        SOCIAL       = 'social',    'Социальное'

    title        = models.CharField(max_length=100, verbose_name='Название')
    description  = models.TextField(verbose_name='Описание условия получения')
    icon         = models.CharField(max_length=50, default='🏆', verbose_name='Иконка/эмодзи')
    badge_color  = models.CharField(max_length=7, default='#FFD700',
                                    verbose_name='Цвет бейджа (hex)')
    ach_type     = models.CharField(max_length=15, choices=AchievementType.choices,
                                    verbose_name='Тип ачивки')
    condition_value = models.PositiveIntegerField(default=1,
                                                  verbose_name='Пороговое значение условия')
    xp_reward    = models.PositiveIntegerField(default=50, verbose_name='Бонус XP')
    is_hidden    = models.BooleanField(default=False, verbose_name='Скрытая')

    class Meta:
        verbose_name        = 'Достижение'
        verbose_name_plural = 'Достижения'

    def __str__(self):
        return f'{self.icon} {self.title}'


class UserAchievement(models.Model):
    """Связь пользователь ↔ полученное достижение."""

    user        = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='achievements', verbose_name='Пользователь')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE,
                                    related_name='earned_by', verbose_name='Достижение')
    earned_at   = models.DateTimeField(auto_now_add=True, verbose_name='Получено')

    class Meta:
        verbose_name        = 'Достижение пользователя'
        verbose_name_plural = 'Достижения пользователей'
        unique_together     = ('user', 'achievement')
        ordering            = ['-earned_at']

    def __str__(self):
        return f'{self.user} → {self.achievement}'


# ---------------------------------------------------------------------------
# Таблица лидеров
# ---------------------------------------------------------------------------

class Leaderboard(models.Model):
    """
    Еженедельный/ежемесячный снимок рейтинга.
    Для реал-тайм рейтинга используем запросы к UserProgress.
    """

    class Period(models.TextChoices):
        WEEKLY  = 'weekly',  'Недельный'
        MONTHLY = 'monthly', 'Месячный'
        ALL_TIME= 'all',     'За всё время'

    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE,
                                    related_name='leaderboards', verbose_name='Класс',
                                    null=True, blank=True)
    user        = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='leaderboard_entries', verbose_name='Пользователь')
    period      = models.CharField(max_length=10, choices=Period.choices,
                                   default=Period.WEEKLY, verbose_name='Период')
    rank        = models.PositiveSmallIntegerField(verbose_name='Место')
    total_xp    = models.PositiveIntegerField(verbose_name='XP за период')
    tasks_done  = models.PositiveIntegerField(default=0, verbose_name='Заданий выполнено')
    recorded_at = models.DateTimeField(auto_now_add=True)
    week_start  = models.DateField(null=True, blank=True, verbose_name='Начало недели')

    class Meta:
        verbose_name        = 'Запись таблицы лидеров'
        verbose_name_plural = 'Таблица лидеров'
        ordering            = ['rank']

    def __str__(self):
        return f'#{self.rank} {self.user} | {self.total_xp} XP ({self.get_period_display()})'


# ---------------------------------------------------------------------------
# Системные логи (для раздела администрирования)
# ---------------------------------------------------------------------------

class SystemLog(models.Model):
    """Системный лог для просмотра администратором."""

    class Level(models.TextChoices):
        INFO    = 'INFO',    'Информация'
        WARNING = 'WARNING', 'Предупреждение'
        ERROR   = 'ERROR',   'Ошибка'

    level      = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    message    = models.TextField(verbose_name='Сообщение')
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='Пользователь')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP-адрес')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Системный лог'
        verbose_name_plural = 'Системные логи'
        ordering            = ['-created_at']

    def __str__(self):
        return f'[{self.level}] {self.created_at:%Y-%m-%d %H:%M} | {self.message[:50]}'