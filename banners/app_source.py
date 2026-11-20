from django.conf import settings

APP_SOURCES = ("direct", "bazaar", "myket")
APP_SOURCE_COOKIE = "cafeclub_app"
APP_SOURCE_MAX_AGE = 60 * 60 * 24 * 400
SESSION_KEY = "app_source"
APP_SOURCE_HEADER = "HTTP_X_APP_SOURCE"


def is_app_webview(request):
    ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
    return "; wv" in ua or " wv)" in ua or "cafeclub" in ua or "amytisapp" in ua


def incoming_source(request):
    header = normalize_source(request.META.get(APP_SOURCE_HEADER))
    if header:
        return header
    query = normalize_source(request.GET.get("app") or request.GET.get("from"))
    if query:
        return query
    if is_app_webview(request) and not read_source(request):
        return "direct"
    return ""

SOURCE_DOWNLOAD_KEYS = {
    "direct": {"ios"},
    "bazaar": {"bazaar"},
    "myket": {"myket"},
}


def normalize_source(value):
    value = (value or "").strip().lower()
    if value in APP_SOURCES:
        return value
    return ""


def read_source(request):
    profile = getattr(getattr(request, "user", None), "club_profile", None) if getattr(request, "user", None) and request.user.is_authenticated else None
    if profile:
        source = normalize_source(getattr(profile, "app_source", ""))
        if source:
            return source
    session_source = normalize_source(request.session.get(SESSION_KEY) if hasattr(request, "session") else "")
    if session_source:
        return session_source
    return normalize_source(request.COOKIES.get(APP_SOURCE_COOKIE))


def persist_source(request, source):
    source = normalize_source(source)
    if not source:
        return ""
    request.session[SESSION_KEY] = source
    request.session.modified = True
    if getattr(request, "user", None) and request.user.is_authenticated:
        profile = getattr(request.user, "club_profile", None)
        if profile and profile.app_source != source:
            profile.app_source = source
            profile.save(update_fields=["app_source"])
    request.app_source = source
    request._set_app_cookie = source
    return source


def set_source_cookie(response, source):
    source = normalize_source(source)
    if not source:
        return response
    response.set_cookie(
        APP_SOURCE_COOKIE,
        source,
        max_age=APP_SOURCE_MAX_AGE,
        path=settings.LANGUAGE_COOKIE_PATH or "/",
        samesite="Lax",
    )
    return response


def filter_downloads(downloads, source):
    keys = SOURCE_DOWNLOAD_KEYS.get(normalize_source(source))
    if not keys:
        return downloads
    return [link for link in downloads if link.key in keys]
