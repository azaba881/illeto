from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    """
    Authentifie par email (USERNAME_FIELD) ou par nom d'utilisateur Django.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        username = username.strip()
        if not username:
            return None

        user = self._get_user(username)
        if user is None:
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def _get_user(self, value: str):
        if "@" in value:
            try:
                return User.objects.get(email__iexact=value)
            except User.DoesNotExist:
                return None
        try:
            return User.objects.get(username__iexact=value)
        except User.DoesNotExist:
            return None
