from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import (
    User, ClassGroup, Subject, Topic, Task, TaskOption,
    UserProgress, LevelAttempt, Achievement, UserAchievement, Leaderboard
)


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------

class UserShortSerializer(serializers.ModelSerializer):
    """Краткое представление пользователя (для вложенных полей)."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'username', 'full_name', 'role', 'avatar',
                  'game_level', 'total_xp']

    def get_full_name(self, obj):
        return obj.get_full_name()


class UserRegisterSerializer(serializers.ModelSerializer):
    """Регистрация нового пользователя."""
    password  = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ['email', 'username', 'first_name', 'last_name',
                  'patronymic', 'password', 'password2', 'role']
        extra_kwargs = {
            'role': {'required': False}
        }

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Пароли не совпадают.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Полный профиль пользователя."""
    full_name           = serializers.SerializerMethodField()
    xp_to_next_level    = serializers.IntegerField(read_only=True)
    xp_progress_percent = serializers.IntegerField(read_only=True)
    class_group_name    = serializers.SerializerMethodField()
    achievements_count  = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name', 'patronymic',
            'full_name', 'role', 'avatar', 'class_group', 'class_group_name',
            'game_level', 'total_xp', 'xp_to_next_level', 'xp_progress_percent',
            'streak_days', 'last_activity', 'date_joined', 'achievements_count'
        ]
        read_only_fields = ['email', 'role', 'total_xp', 'game_level', 'date_joined']

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_class_group_name(self, obj):
        return obj.class_group.name if obj.class_group else None

    def get_achievements_count(self, obj):
        return obj.achievements.count()


class ChangePasswordSerializer(serializers.Serializer):
    """Смена пароля."""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Неверный текущий пароль.')
        return value


# ---------------------------------------------------------------------------
# Классы
# ---------------------------------------------------------------------------

class ClassGroupSerializer(serializers.ModelSerializer):
    teacher_name   = serializers.SerializerMethodField()
    students_count = serializers.SerializerMethodField()

    class Meta:
        model  = ClassGroup
        fields = ['id', 'name', 'description', 'teacher', 'teacher_name',
                  'students_count', 'created_at', 'is_active']
        read_only_fields = ['created_at']

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() if obj.teacher else None

    def get_students_count(self, obj):
        return obj.students.count()


# ---------------------------------------------------------------------------
# Контент
# ---------------------------------------------------------------------------

class TaskOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TaskOption
        fields = ['id', 'text', 'is_correct', 'match_key', 'match_value', 'order']
        # is_correct скрыт для учеников (фильтрация в ViewSet)


class TaskOptionStudentSerializer(serializers.ModelSerializer):
    """Вариант ответа без поля is_correct (для учеников)."""
    class Meta:
        model  = TaskOption
        fields = ['id', 'text', 'match_key', 'order']


class TaskSerializer(serializers.ModelSerializer):
    """Задание для учителей (с правильными ответами)."""
    options      = TaskOptionSerializer(many=True, read_only=True)
    topic_title  = serializers.CharField(source='topic.title', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)

    class Meta:
        model  = Task
        fields = [
            'id', 'topic', 'topic_title', 'title', 'description',
            'task_type', 'difficulty', 'difficulty_display', 'xp_reward',
            'order', 'is_active', 'created_at', 'updated_at',
            # math_path поля
            'start_value', 'target_value', 'operation_1', 'operation_2',
            'max_steps', 'optimal_steps',
            # test поля
            'options', 'correct_answer_text'
        ]


class TaskStudentSerializer(serializers.ModelSerializer):
    """Задание для учеников (без правильных ответов в тестах)."""
    options     = TaskOptionStudentSerializer(many=True, read_only=True)
    topic_title = serializers.CharField(source='topic.title', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)

    class Meta:
        model  = Task
        fields = [
            'id', 'topic', 'topic_title', 'title', 'description',
            'task_type', 'difficulty', 'difficulty_display', 'xp_reward',
            'order',
            'start_value', 'target_value', 'operation_1', 'operation_2',
            'max_steps', 'optimal_steps',
            'options',
        ]


class TopicSerializer(serializers.ModelSerializer):
    tasks_count  = serializers.SerializerMethodField()
    subject_title= serializers.CharField(source='subject.title', read_only=True)

    class Meta:
        model  = Topic
        fields = ['id', 'subject', 'subject_title', 'title', 'description',
                  'theory_text', 'order', 'tasks_count', 'created_at']

    def get_tasks_count(self, obj):
        return obj.tasks.filter(is_active=True).count()


class SubjectSerializer(serializers.ModelSerializer):
    topics       = TopicSerializer(many=True, read_only=True)
    topics_count = serializers.SerializerMethodField()

    class Meta:
        model  = Subject
        fields = ['id', 'title', 'description', 'order', 'icon',
                  'topics_count', 'topics']

    def get_topics_count(self, obj):
        return obj.topics.count()


# ---------------------------------------------------------------------------
# Прогресс и попытки
# ---------------------------------------------------------------------------

class UserProgressSerializer(serializers.ModelSerializer):
    topic_title        = serializers.CharField(source='topic.title', read_only=True)
    subject_title      = serializers.CharField(source='topic.subject.title', read_only=True)
    completion_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model  = UserProgress
        fields = [
            'id', 'topic', 'topic_title', 'subject_title',
            'tasks_completed', 'tasks_total', 'total_errors',
            'best_score', 'total_xp_earned', 'is_completed',
            'completion_percent', 'started_at', 'completed_at', 'updated_at'
        ]


class LevelAttemptSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source='task.title', read_only=True)
    task_type  = serializers.CharField(source='task.task_type', read_only=True)

    class Meta:
        model  = LevelAttempt
        fields = [
            'id', 'task', 'task_title', 'task_type',
            'is_success', 'errors_made', 'steps_taken',
            'xp_earned', 'time_spent', 'solution_path',
            'started_at', 'finished_at'
        ]
        read_only_fields = ['started_at']


class SubmitAttemptSerializer(serializers.Serializer):
    """
    Данные для сохранения результата попытки.
    Поддерживает все типы заданий.
    """
    task_id        = serializers.IntegerField()
    # Для math_path
    solution_path  = serializers.ListField(child=serializers.IntegerField(),
                                           required=False)
    steps_taken    = serializers.IntegerField(required=False, default=0)
    # Для тестов
    selected_option_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )
    # Для text_input
    text_answer    = serializers.CharField(required=False, allow_blank=True)
    # Общие
    time_spent     = serializers.IntegerField(required=False, default=0)
    errors_made    = serializers.IntegerField(required=False, default=0)


# ---------------------------------------------------------------------------
# Достижения
# ---------------------------------------------------------------------------

class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Achievement
        fields = ['id', 'title', 'description', 'icon', 'badge_color',
                  'ach_type', 'condition_value', 'xp_reward', 'is_hidden']


class UserAchievementSerializer(serializers.ModelSerializer):
    achievement = AchievementSerializer(read_only=True)

    class Meta:
        model  = UserAchievement
        fields = ['id', 'achievement', 'earned_at']


# ---------------------------------------------------------------------------
# Таблица лидеров
# ---------------------------------------------------------------------------

class LeaderboardSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)

    class Meta:
        model  = Leaderboard
        fields = ['rank', 'user', 'total_xp', 'tasks_done', 'period',
                  'recorded_at', 'week_start']