from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = UserCreationForm(request.POST or None)
    form.fields["username"].label = "نام کاربری"
    form.fields["password1"].label = "رمز عبور"
    form.fields["password2"].label = "تکرار رمز عبور"
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        next_url = request.POST.get("next") or request.GET.get("next") or ""
        if next_url.startswith("/") and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("home")
    return render(
        request,
        "account/register.html",
        {"form": form, "next": request.GET.get("next") or request.POST.get("next") or ""},
    )


@require_POST
def save_username(request):
    username = (request.POST.get("username") or "").strip()[:40]
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not next_url.startswith("/") or not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = "/"
    if not username:
        return redirect(next_url)
    if request.user.is_authenticated:
        field = User._meta.get_field("username")
        try:
            field.clean(username, request.user)
        except ValidationError:
            return redirect(next_url)
        clash = User.objects.filter(username=username).exclude(pk=request.user.pk)
        if not clash.exists():
            request.user.username = username
            request.user.save(update_fields=["username"])
    else:
        request.session["profile_username"] = username
        request.session.modified = True
    return redirect(next_url)
