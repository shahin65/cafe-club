from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import check_for_language
from django.views.decorators.http import require_POST
from django.views.i18n import LANGUAGE_QUERY_PARAMETER

from banners.catalog import rename_package
from banners.pay_views import start_checkout


def _safe_next(request, fallback="profile"):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url.startswith("/") and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    if not fallback:
        return ""
    from django.urls import reverse

    return reverse(fallback)


def login_page(request):
    return redirect("profile")


def register(request):
    return redirect("profile")


def _display_name_changes(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "club_profile", None)
        return int(getattr(profile, "display_name_changes", 0) or 0)
    try:
        return int(request.session.get("display_name_changes") or 0)
    except (TypeError, ValueError):
        return 0


def _current_display_name(request):
    if request.user.is_authenticated:
        profile = getattr(request.user, "club_profile", None)
        return ((profile.display_name if profile else "") or "").strip()
    return (request.session.get("profile_display_name") or "").strip()


def _apply_free_display_name(request, display_name):
    if request.user.is_authenticated:
        profile = getattr(request.user, "club_profile", None)
        if not profile:
            return
        profile.display_name = display_name
        profile.display_name_changes = (profile.display_name_changes or 0) + 1
        profile.save(update_fields=["display_name", "display_name_changes"])
        return
    request.session["profile_display_name"] = display_name
    request.session["display_name_changes"] = _display_name_changes(request) + 1
    request.session.modified = True


@require_POST
def save_username(request):
    username = (request.POST.get("username") or "").strip()[:40]
    display_name = (request.POST.get("display_name") or "").strip()[:40]
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not next_url.startswith("/") or not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = "/"
    if request.user.is_authenticated and username:
        field = User._meta.get_field("username")
        try:
            field.clean(username, request.user)
        except ValidationError:
            return redirect(next_url)
        clash = User.objects.filter(username=username).exclude(pk=request.user.pk)
        if not clash.exists():
            request.user.username = username
            request.user.save(update_fields=["username"])
    elif not request.user.is_authenticated and username:
        request.session["profile_username"] = username
        request.session.modified = True
    current = _current_display_name(request)
    if not display_name or display_name == current:
        return redirect(next_url)
    if _display_name_changes(request) >= 1:
        request.session["pending_paid_display_name"] = display_name
        request.session.modified = True
        if not request.user.is_authenticated:
            messages.info(
                request,
                "ویرایش دوم نام نمایشی ۵۰٬۰۰۰ تومان است. ابتدا با تلگرام یا بله ثبت‌نام کنید و بعد پرداخت کنید.",
            )
            return redirect("profile")
        package = rename_package()
        if not package:
            messages.error(request, "محصول ویرایش نام در دسترس نیست.")
            return redirect("profile")
        return start_checkout(
            request,
            package,
            fail_url="profile",
            return_to="profile",
            payload={"display_name": display_name},
        )
    _apply_free_display_name(request, display_name)
    messages.success(request, "نام نمایشی ذخیره شد. ویرایش بعدی ۵۰٬۰۰۰ تومان است.")
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
