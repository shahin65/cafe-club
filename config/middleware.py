from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import check_for_language

from banners.accounts import user_is_blocked
from banners.app_source import incoming_source, persist_source, read_source, set_source_cookie
from banners.auth_views import language_prefixed_path
from banners.digits import persianize_html_digits

_UNPREFIXED_ROOTS = (
    "/admin",
    "/i18n/",
    "/account/google/",
    "/favicon.ico",
    "/manifest.webmanifest",
    "/sw.js",
    "/robots.txt",
    "/sitemap.xml",
    "/staff/",
    "/static/",
    "/media/",
    "/app/",
)


def _is_unprefixed_root(path):
    if path == "/admin" or path.startswith("/admin/"):
        return True
    return any(path == root or path.startswith(root) for root in _UNPREFIXED_ROOTS)


class PersistChosenLanguageMiddleware(MiddlewareMixin):
    """Keep the language chosen in settings even after Back to an unprefixed URL."""

    def process_request(self, request):
        path = request.path
        if _is_unprefixed_root(path):
            return
        if translation.get_language_from_path(request.path_info):
            return
        cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if not cookie or not check_for_language(cookie) or cookie == settings.LANGUAGE_CODE:
            return
        prefixed = language_prefixed_path(path, cookie)
        if prefixed == path:
            return
        query = request.META.get("QUERY_STRING")
        return HttpResponseRedirect(f"{prefixed}?{query}" if query else prefixed)


class ForceAdminPersianMiddleware(MiddlewareMixin):
    """Keep the administration panel in Persian even if the public site is English."""

    def process_request(self, request):
        path = request.path
        if path == "/admin" or path.startswith("/admin/"):
            translation.activate("fa")
            request.LANGUAGE_CODE = "fa"


class AttachAppSourceMiddleware(MiddlewareMixin):
    """Remember whether the visitor opened Cafe Club from direct, Bazaar, or Myket."""

    def process_request(self, request):
        incoming = incoming_source(request)
        if incoming:
            persist_source(request, incoming)
            return
        source = read_source(request)
        request.app_source = source
        if source and getattr(request, "user", None) and request.user.is_authenticated:
            profile = getattr(request.user, "club_profile", None)
            if profile and profile.app_source != source:
                persist_source(request, source)

    def process_response(self, request, response):
        source = getattr(request, "_set_app_cookie", None)
        if source:
            set_source_cookie(response, source)
        return response


_MAINTENANCE_ALLOWED = (
    "/admin",
    "/static/",
    "/media/",
    "/favicon.ico",
    "/manifest.webmanifest",
    "/sw.js",
    "/robots.txt",
    "/sitemap.xml",
)


def _maintenance_path_allowed(path):
    if path == "/admin" or path.startswith("/admin/"):
        return True
    return any(path == root or path.startswith(root) for root in _MAINTENANCE_ALLOWED)


class BlockedAccountMiddleware(MiddlewareMixin):
    """Keep blocked accounts out of the public site even if a session is open."""

    def process_request(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return
        if not user_is_blocked(user):
            return
        if _maintenance_path_allowed(request.path):
            return
        from django.contrib.auth import logout

        logout(request)
        from django.urls import reverse

        return HttpResponseRedirect(reverse("login"))


class MaintenanceModeMiddleware(MiddlewareMixin):
    """Close the public site while staff turn on maintenance for an update."""

    def process_request(self, request):
        if _maintenance_path_allowed(request.path):
            return
        try:
            from banners.models import SiteSettings

            closed = SiteSettings.objects.filter(pk=1, maintenance_mode=True).exists()
        except Exception:
            return
        if not closed:
            return
        return render(request, "banners/maintenance.html", status=503)


class PersianDigitsMiddleware(MiddlewareMixin):
    """Show Western digits as Persian numerals on the public Farsi site."""

    def process_response(self, request, response):
        language = getattr(request, "LANGUAGE_CODE", "") or ""
        if not language.startswith("fa"):
            return response
        path = request.path or ""
        if path == "/admin" or path.startswith("/admin/") or path.startswith("/static/") or path.startswith("/media/"):
            return response
        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type or not hasattr(response, "content"):
            return response
        try:
            charset = response.charset or "utf-8"
            html = response.content.decode(charset)
        except (LookupError, UnicodeDecodeError):
            return response
        converted = persianize_html_digits(html)
        if converted == html:
            return response
        response.content = converted.encode(charset)
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))
        return response
