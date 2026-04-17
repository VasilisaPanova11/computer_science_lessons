from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, ClassGroup, Subject, Topic, Task, TaskOption,
    UserProgress, LevelAttempt, Achievement, UserAchievement,
    Leaderboard, SystemLog
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ['username', 'email', 'get_full_name', 'role',
                     'class_group', 'game_level', 'total_xp', 'is_active']
    list_filter   = ['role', 'is_active', 'class_group']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering      = ['last_name']

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Личные данные', {'fields': ('first_name', 'last_name', 'patronymic', 'avatar')}),
        ('Роль и класс', {'fields': ('role', 'class_group')}),
        ('Геймификация', {'fields': ('total_xp', 'game_level', 'streak_days', 'last_activity')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                      'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'first_name', 'last_name',
                       'role', 'password1', 'password2'),
        }),
    )
    readonly_fields = ['date_joined', 'last_login', 'total_xp', 'game_level']


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display  = ['name', 'teacher', 'students_count', 'is_active', 'created_at']
    list_filter   = ['is_active', 'teacher']
    search_fields = ['name']

    def students_count(self, obj):
        return obj.students.count()
    students_count.short_description = 'Учеников'


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'order', 'topics_count']
    ordering     = ['order']

    def topics_count(self, obj):
        return obj.topics.count()
    topics_count.short_description = 'Тем'


class TaskOptionInline(admin.TabularInline):
    model  = TaskOption
    extra  = 3
    fields = ['text', 'is_correct', 'match_key', 'match_value', 'order']


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display  = ['title', 'subject', 'order', 'tasks_count', 'created_by']
    list_filter   = ['subject']
    search_fields = ['title']
    ordering      = ['subject', 'order']

    def tasks_count(self, obj):
        return obj.tasks.count()
    tasks_count.short_description = 'Заданий'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display  = ['title', 'topic', 'task_type', 'difficulty',
                     'xp_reward', 'is_active', 'created_at']
    list_filter   = ['task_type', 'difficulty', 'is_active', 'topic__subject']
    search_fields = ['title', 'description']
    inlines       = [TaskOptionInline]

    fieldsets = (
        ('Основное', {'fields': ('topic', 'title', 'description', 'task_type',
                                  'difficulty', 'xp_reward', 'order', 'is_active')}),
        ('Математический путь', {
            'fields': ('start_value', 'target_value', 'operation_1',
                       'operation_2', 'max_steps', 'optimal_steps'),
            'classes': ('collapse',),
        }),
        ('Текстовый ответ', {
            'fields': ('correct_answer_text',),
            'classes': ('collapse',),
        }),
    )


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ['icon_display', 'title', 'ach_type', 'condition_value',
                    'xp_reward', 'is_hidden']
    list_filter  = ['ach_type', 'is_hidden']

    def icon_display(self, obj):
        return format_html('<span style="font-size:1.5em">{}</span>', obj.icon)
    icon_display.short_description = 'Иконка'


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ['user', 'achievement', 'earned_at']
    list_filter  = ['achievement']


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'topic', 'tasks_completed', 'tasks_total',
                    'total_errors', 'is_completed']
    list_filter  = ['is_completed', 'topic__subject']
    readonly_fields = ['started_at', 'updated_at']


@admin.register(LevelAttempt)
class LevelAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'task', 'is_success', 'errors_made',
                    'xp_earned', 'time_spent', 'started_at']
    list_filter  = ['is_success', 'task__task_type']
    readonly_fields = ['started_at']


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display  = ['level', 'message_short', 'user', 'ip_address', 'created_at']
    list_filter   = ['level']
    readonly_fields = ['created_at']

    def message_short(self, obj):
        return obj.message[:80]
    message_short.short_description = 'Сообщение'


# Настройка заголовка панели администратора
admin.site.site_header = 'ИС Геймификация Информатика'
admin.site.site_title  = 'Геймификация'
admin.site.index_title = 'Панель администратора'