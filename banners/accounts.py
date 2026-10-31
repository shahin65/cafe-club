from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
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


class SimpleClubRegisterForm(forms.Form):
    username = forms.CharField(
        label="نام کاربری",
        max_length=40,
        min_length=1,
        error_messages={"required": "نام کاربری را وارد کنید."},
    )
    password = forms.CharField(
        label="گذرواژه",
        min_length=6,
        max_length=128,
        widget=forms.PasswordInput,
        error_messages={
            "required": "گذرواژه را وارد کنید.",
            "min_length": "گذرواژه حداقل ۶ نویسه باشد.",
        },
    )

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("نام کاربری را وارد کنید.")
        field = User._meta.get_field("username")
        username = field.clean(username, None)
        if User.objects.filter(username=username).exists():
            raise ValidationError("این نام کاربری قبلاً گرفته شده است.")
        return username

    def save(self):
        user = User(username=self.cleaned_data["username"])
        user.set_password(self.cleaned_data["password"])
        user.save()
        return user
