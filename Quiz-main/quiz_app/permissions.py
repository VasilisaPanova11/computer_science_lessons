from rest_framework.permissions import BasePermission
from .models import User


class IsTeacherOrAdmin(BasePermission):
    """Доступ только для учителей и администраторов."""
    message = 'Доступ разрешён только учителям и администраторам.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in (User.Role.TEACHER, User.Role.ADMIN)
        )


class IsAdmin(BasePermission):
    """Доступ только для администраторов."""
    message = 'Доступ разрешён только администраторам.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == User.Role.ADMIN
        )


class IsOwnerOrTeacher(BasePermission):
    """Владелец объекта, учитель или администратор."""
    def has_object_permission(self, request, view, obj):
        if request.user.role in (User.Role.TEACHER, User.Role.ADMIN):
            return True
        # Проверяем, что объект принадлежит пользователю
        return getattr(obj, 'user', None) == request.user