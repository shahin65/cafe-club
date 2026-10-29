from django.templatetags.static import static

from scenarios.branding import PRESET_LABELS, PRESETS, current_card_logo
from scenarios.dealing import SESSION_KEY, deal_is_active


def role_deal(request):
    return {"role_deal_active": deal_is_active(request.session.get(SESSION_KEY))}


def branding(request):
    choice = current_card_logo(request)
    club_profile = None
    profile_display_name = ""
    if request.user.is_authenticated:
        profile_username = request.user.get_username()
        club_profile = getattr(request.user, "club_profile", None)
        profile_display_name = (club_profile.display_name or "").strip() if club_profile else ""
        profile_shown_name = club_profile.shown_name() if club_profile else profile_username
    else:
        profile_username = (request.session.get("profile_username") or "").strip()
        profile_display_name = (request.session.get("profile_display_name") or "").strip()
        profile_shown_name = profile_display_name or profile_username
    app_source = getattr(request, "app_source", "") or ""
    return {
        "card_back_logo": choice["url"],
        "card_logo_choice": choice,
        "card_logo_presets": [
            {"key": key, "file": filename, "url": static(filename), "label": PRESET_LABELS.get(key, key)}
            for key, filename in PRESETS.items()
        ],
        "profile_username": profile_username,
        "profile_display_name": profile_display_name,
        "profile_shown_name": profile_shown_name,
        "club_profile": club_profile,
        "app_source": app_source,
        "from_installed_app": bool(app_source),
    }
