"""
URL-маршруты приложения quiz_app.
Все маршруты именованы — используй {% url 'name' %} в шаблонах.
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Аутентификация ──────────────────────────────────────────────
    # GET/POST  /login/          → форма входа
    path('login/',          views.login_view,          name='login'),
    # GET/POST  /register/       → форма регистрации
    path('register/',       views.register_view,       name='register'),
    # POST      /logout/         → выход и редирект на /login/
    path('logout/',         views.logout_view,         name='logout'),
    # GET/POST  /password-reset/ → запрос письма для сброса пароля
    path('password-reset/', views.password_reset_view, name='password_reset'),

    # ── Главная (редирект на дашборд) ───────────────────────────────
    # GET /  → если авторизован: /dashboard/, иначе /login/
    path('', lambda req: (
        __import__('django.shortcuts', fromlist=['redirect'])
        .redirect('dashboard' if req.user.is_authenticated else 'login')
    ), name='home'),

    # ── Дашборд ─────────────────────────────────────────────────────
    # GET /dashboard/  → дашборд (содержимое зависит от роли)
    path('dashboard/',      views.dashboard_view,      name='dashboard'),

    # ── Учебный контент ─────────────────────────────────────────────
    # GET /subjects/                → список разделов с темами
    path('subjects/',               views.subjects_view,      name='subjects'),
    # GET /subjects/<id>/           → детальная страница темы
    path('subjects/<int:topic_id>/', views.topic_detail_view, name='topic_detail'),

    # ── Игровой экран ───────────────────────────────────────────────
    # GET  /game/<task_id>/        → экран задания
    path('game/<int:task_id>/',          views.game_view,          name='game'),
    # POST /game/<task_id>/submit/ → AJAX: отправить ответ, вернуть JSON
    path('game/<int:task_id>/submit/',   views.submit_answer_view, name='submit_answer'),

    # ── Профиль ─────────────────────────────────────────────────────
    # GET/POST /profile/  → просмотр и редактирование профиля
    path('profile/',        views.profile_view,        name='profile'),

    # ── Таблица лидеров ─────────────────────────────────────────────
    # GET /leaderboard/            → общий рейтинг
    # GET /leaderboard/?class=<id> → рейтинг конкретного класса
    path('leaderboard/',    views.leaderboard_view,    name='leaderboard'),

    # ── Достижения ──────────────────────────────────────────────────
    # GET /achievements/  → все ачивки с отметками «получено»
    path('achievements/',   views.achievements_view,   name='achievements'),

    # ── Управление классами (учитель/администратор) ─────────────────
    # GET/POST /classes/              → список классов + создание
    path('classes/',                    views.classes_view,      name='classes'),
    # GET/POST /classes/<id>/          → детали класса, управление учениками
    path('classes/<int:class_id>/',     views.class_detail_view, name='class_detail'),

    # ── Создание заданий (учитель/администратор) ─────────────────────
    # GET/POST /subjects/<id>/new-task/ → форма создания задания
    path('subjects/<int:topic_id>/new-task/', views.task_create_view, name='task_create'),
]