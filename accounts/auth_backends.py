from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()

        if not username or not password:
            return None

        # First, try an exact username match.
        user = User.objects.filter(username=username).first()

        # If no username matches, try the email address.
        if user is None:
            matching_users = User.objects.filter(
                email__iexact=username
            ).exclude(email="")

            # Only allow email login when exactly one account matches.
            if matching_users.count() == 1:
                user = matching_users.first()
            else:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
