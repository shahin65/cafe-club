from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


def user_is_blocked(user):
    if not user:
        return False
    profile = getattr(user, "club_profile", None)
    return bool(profile and profile.is_blocked)


class ClubLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        if user_is_blocked(user):
            raise ValidationError("این اکانت مسدود شده است.", code="blocked")
        super().confirm_login_allowed(user)
