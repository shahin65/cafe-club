from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import check_for_language
from django.views.decorators.http import require_POST
from django.views.i18n import LANGUAGE_QUERY_PARAMETER


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


def language_prefixed_path(path, language):
    path = path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    had_slash = path.endswith("/")
    language_codes = {code for code, _name in settings.LANGUAGES}
    parts = [part for part in path.split("/") if part != ""]
    while parts and parts[0] in language_codes:
        parts = parts[1:]
    path = "/" + "/".join(parts) if parts else "/"
    if parts and had_slash and not path.endswith("/"):
        path += "/"
    if language != settings.LANGUAGE_CODE:
        if path == "/":
            return f"/{language}/"
        return f"/{language}{path}"
    return path


@require_POST
def set_language(request):
    next_url = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = "/"
    language = request.POST.get(LANGUAGE_QUERY_PARAMETER)
    parsed = urlsplit(next_url)
    if language and check_for_language(language):
        path = language_prefixed_path(parsed.path or "/", language)
        next_url = urlunsplit(("", parsed.netloc, path, parsed.query, parsed.fragment))
        if parsed.netloc:
            next_url = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
        response = HttpResponseRedirect(next_url)
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
        return response
    return HttpResponseRedirect(next_url)
