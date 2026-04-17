from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenVerifyView
)
from . import views

router = DefaultRouter()
router.register(r'users',        views.UserViewSet,         basename='user')
router.register(r'classes',      views.ClassGroupViewSet,   basename='classgroup')
router.register(r'subjects',     views.SubjectViewSet,      basename='subject')
router.register(r'topics',       views.TopicViewSet,        basename='topic')
router.register(r'tasks',        views.TaskViewSet,         basename='task')
router.register(r'progress',     views.UserProgressViewSet, basename='progress')
router.register(r'achievements', views.AchievementViewSet,  basename='achievement')

urlpatterns = [
    # JWT аутентификация
    path('auth/login/',   TokenObtainPairView.as_view(), name='token_obtain'),
    path('auth/refresh/', TokenRefreshView.as_view(),    name='token_refresh'),
    path('auth/verify/',  TokenVerifyView.as_view(),     name='token_verify'),

    # Регистрация и профиль
    path('auth/register/',        views.RegisterView.as_view(),        name='register'),
    path('auth/password-reset/',  views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('profile/',              views.ProfileView.as_view(),          name='profile'),
    path('profile/password/',     views.ChangePasswordView.as_view(),   name='change_password'),

    # Дашборд
    path('dashboard/',            views.DashboardView.as_view(),       name='dashboard'),

    # Достижения текущего пользователя
    path('my-achievements/',      views.UserAchievementView.as_view(), name='my_achievements'),

    # Таблица лидеров
    path('leaderboard/',          views.LeaderboardView.as_view(),     name='leaderboard'),

    # ViewSets
    path('', include(router.urls)),
]