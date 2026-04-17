"""
Бэкенд аутентификации по email вместо username.
"""

from django.contrib.auth.backends import ModelBackend
from .models import User


class EmailBackend(ModelBackend):
    """Позволяет входить по email + пароль."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        # username здесь содержит email (Django передаёт первый аргумент как username)
        try:
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None