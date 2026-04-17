from django.core.management.base import BaseCommand
from quiz_app.models import (
    User, ClassGroup, Subject, Topic, Task, TaskOption, Achievement
)


class Command(BaseCommand):
    help = 'Заполняет базу данных начальными тестовыми данными'

    def handle(self, *args, **options):
        self.stdout.write('Создание начальных данных...')
        self._create_achievements()
        self._create_users()
        self._create_content()
        self.stdout.write(self.style.SUCCESS('Готово! База данных заполнена.'))

    def _create_achievements(self):
        achievements = [
            {'title': 'Первые шаги',   'description': 'Выполни первое задание',
             'icon': '🎯', 'ach_type': 'completion', 'condition_value': 1,  'xp_reward': 20},
            {'title': 'Пятёрочник',    'description': '5 заданий подряд без ошибок',
             'icon': '⭐', 'ach_type': 'accuracy',   'condition_value': 5,  'xp_reward': 50},
            {'title': 'Спидраннер',    'description': 'Реши задание менее чем за 15 секунд',
             'icon': '⚡', 'ach_type': 'speed',      'condition_value': 15, 'xp_reward': 30},
            {'title': 'Упорный',       'description': '7 дней занятий подряд',
             'icon': '🔥', 'ach_type': 'streak',     'condition_value': 7,  'xp_reward': 100},
            {'title': 'Опытный',       'description': 'Набери 500 XP',
             'icon': '💎', 'ach_type': 'score',      'condition_value': 500, 'xp_reward': 50},
            {'title': 'Мастер',        'description': 'Заверши 10 тем',
             'icon': '🏆', 'ach_type': 'completion', 'condition_value': 10, 'xp_reward': 200},
        ]
        for ach_data in achievements:
            Achievement.objects.get_or_create(title=ach_data['title'], defaults=ach_data)
        self.stdout.write(f'  ✓ Создано {len(achievements)} ачивок')

    def _create_users(self):
        # Администратор
        if not User.objects.filter(email='admin@quiz.ru').exists():
            User.objects.create_superuser(
                email='admin@quiz.ru', username='admin',
                first_name='Администратор', last_name='Системы',
                password='admin123'
            )

        # Учитель
        teacher, _ = User.objects.get_or_create(
            email='teacher@quiz.ru',
            defaults={
                'username': 'teacher_ivanova',
                'first_name': 'Мария', 'last_name': 'Иванова',
                'role': User.Role.TEACHER,
            }
        )
        if _:
            teacher.set_password('teacher123')
            teacher.save()

        # Класс
        class_group, _ = ClassGroup.objects.get_or_create(
            name='9А', defaults={'teacher': teacher, 'description': 'Девятый А класс'}
        )

        # Несколько учеников
        students_data = [
            ('student1@quiz.ru', 'student_petrov',   'Иван',   'Петров',   150),
            ('student2@quiz.ru', 'student_sidorova', 'Анна',   'Сидорова', 280),
            ('student3@quiz.ru', 'student_kozlov',   'Максим', 'Козлов',   90),
        ]
        for email, username, first, last, xp in students_data:
            student, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': username, 'first_name': first, 'last_name': last,
                    'role': User.Role.STUDENT, 'class_group': class_group,
                    'total_xp': xp,
                }
            )
            if created:
                student.set_password('student123')
                student.recalculate_level()
                student.save()

        self.stdout.write('  ✓ Пользователи созданы')

    def _create_content(self):
        # Разделы
        subject_data = [
            ('Системы счисления', 'Перевод между системами счисления', '💻', 0),
            ('Алгоритмы',         'Основы алгоритмизации',             '🔄', 1),
            ('Логика',            'Булева алгебра и логические схемы', '⚙️', 2),
        ]
        for title, desc, icon, order in subject_data:
            subject, _ = Subject.objects.get_or_create(
                title=title,
                defaults={'description': desc, 'icon': icon, 'order': order}
            )

            # Создаём темы и задания для первого раздела
            if title == 'Системы счисления' and _:
                self._create_math_path_tasks(subject)

        self.stdout.write('  ✓ Учебный контент создан')

    def _create_math_path_tasks(self, subject):
        """Создаёт математические задания для темы «Системы счисления»."""
        teacher = User.objects.filter(role=User.Role.TEACHER).first()

        topic, _ = Topic.objects.get_or_create(
            title='Математический путь: степени двойки',
            subject=subject,
            defaults={
                'description': 'Переход между значениями с помощью двух операций',
                'theory_text': (
                    'В информатике часто используются степени числа 2: 1, 2, 4, 8, 16, 32...\n'
                    'В этом задании нужно перейти от начального числа к целевому, '
                    'используя только две разрешённые операции.'
                ),
                'order': 1,
                'created_by': teacher,
            }
        )

        tasks = [
            {
                'title': 'От 1 до 16',
                'description': 'Перейди от 1 к 16, используя операции «×2» и «+1».',
                'start_value': 1,   'target_value': 16,
                'operation_1': '*2', 'operation_2': '+1',
                'max_steps': 8,     'optimal_steps': 4,
                'difficulty': 1,    'xp_reward': 10,
                'order': 1,
            },
            {
                'title': 'От 3 до 24',
                'description': 'Перейди от 3 к 24, используя операции «×2» и «+3».',
                'start_value': 3,   'target_value': 24,
                'operation_1': '*2', 'operation_2': '+3',
                'max_steps': 10,    'optimal_steps': 3,
                'difficulty': 2,    'xp_reward': 20,
                'order': 2,
            },
            {
                'title': 'От 5 до 100',
                'description': 'Перейди от 5 к 100, используя «×2» и «+10».',
                'start_value': 5,   'target_value': 100,
                'operation_1': '*2', 'operation_2': '+10',
                'max_steps': 15,    'optimal_steps': 6,
                'difficulty': 3,    'xp_reward': 30,
                'order': 3,
            },
            {
                'title': 'Обратный путь: от 128 к 1',
                'description': 'Перейди от 128 к 1, используя «÷2» и «-1».',
                'start_value': 128, 'target_value': 1,
                'operation_1': '/2', 'operation_2': '-1',
                'max_steps': 12,    'optimal_steps': 7,
                'difficulty': 2,    'xp_reward': 20,
                'order': 4,
            },
        ]

        for task_data in tasks:
            Task.objects.get_or_create(
                title=task_data['title'],
                topic=topic,
                defaults={
                    **task_data,
                    'task_type': Task.TaskType.MATH_PATH,
                    'is_active': True,
                    'created_by': teacher,
                }
            )