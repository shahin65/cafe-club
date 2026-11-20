from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


COMMENT_RECEIVED = "نظر شما با موفقیت ثبت شد و پس از بازبینی در سایت منتشر می‌شود."


def comment_author_name(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "club_profile", None)
        if profile:
            return (profile.shown_name() or "")[:40]
        return (request.user.get_username() or "")[:40]
    return (request.POST.get("author_name") or "").strip()[:40]


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
