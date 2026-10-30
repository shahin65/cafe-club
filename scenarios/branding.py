from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.shortcuts import redirect
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_POST
from PIL import Image

from scenarios.models import CardBranding

CARD_LOGO_SESSION = "card_logo"
CUSTOM_KEY = "custom"
PRESETS = {
    "cafeclub": "Logo.png",
    "dun": "Logo-Dun.png",
    "legendary": "Logo-Legendary.jpg",
    "win": "Logo-Win.jpg",
}
PRESET_LABELS = {
    "cafeclub": "کافه کلاب",
    "dun": "Dun",
    "legendary": "Legendary",
    "win": "Win",
}
ICON_MAX = 2 * 1024 * 1024
ICON_TYPES = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png", ".webp": ".webp", ".gif": ".gif"}


def preset_file(key):
    return PRESETS.get(key, "")


def default_logo_url():
    return static("Logo.png")


def _choice_from_branding(branding):
    if branding.preset in PRESETS:
        return {"kind": "preset", "key": branding.preset, "url": static(PRESETS[branding.preset])}
    if branding.image:
        return {"kind": "upload", "key": CUSTOM_KEY, "url": branding.image.url}
    return None


def _choice_from_session(data):
    data = data or {}
    if data.get("kind") == "upload" and data.get("path"):
        if default_storage.exists(data["path"]):
            return {"kind": "upload", "key": CUSTOM_KEY, "url": default_storage.url(data["path"])}
    key = data.get("key")
    if data.get("kind") == "preset" and key in PRESETS:
        return {"kind": "preset", "key": key, "url": static(PRESETS[key])}
    return None


def current_card_logo(request):
    if request.user.is_authenticated:
        branding = CardBranding.objects.filter(user=request.user).first()
        if branding:
            choice = _choice_from_branding(branding)
            if choice:
                return choice
    choice = _choice_from_session(request.session.get(CARD_LOGO_SESSION))
    if choice:
        return choice
    return {"kind": "preset", "key": "cafeclub", "url": default_logo_url()}


def custom_logo_choice(request):
    if request.user.is_authenticated:
        branding = CardBranding.objects.filter(user=request.user).first()
        if branding and branding.image:
            return {"key": CUSTOM_KEY, "url": branding.image.url, "label": "لوگوی من"}
    session = request.session.get(CARD_LOGO_SESSION) or {}
    if session.get("kind") == "upload" and session.get("path") and default_storage.exists(session["path"]):
        return {"key": CUSTOM_KEY, "url": default_storage.url(session["path"]), "label": "لوگوی من"}
    return None


def _store_upload(prefix, upload):
    if not upload or upload.size > ICON_MAX:
        return None
    suffix = ICON_TYPES.get(Path(upload.name or "").suffix.lower())
    if not suffix:
        return None
    raw = upload.read()
    if not raw:
        return None
    try:
        Image.open(BytesIO(raw)).verify()
    except Exception:
        return None
    return default_storage.save(f"card_logos/{prefix}/{uuid4().hex}{suffix}", ContentFile(raw))


def _save_session(request, payload):
    request.session[CARD_LOGO_SESSION] = payload
    request.session.modified = True


def _save_user(request, preset="", image_path=None):
    if not request.user.is_authenticated:
        return
    branding, _created = CardBranding.objects.get_or_create(user=request.user)
    branding.preset = preset
    if image_path is not None:
        branding.image = image_path
    branding.save()


def _is_verified(request):
    profile = getattr(request.user, "club_profile", None) if request.user.is_authenticated else None
    return bool(profile and profile.is_verified)


def _home_logo_redirect():
    return redirect(f"{reverse('home')}?logo=1")


@require_POST
def save_card_logo(request):
    preset = (request.POST.get("preset") or "").strip()
    if preset in PRESETS:
        _save_session(request, {"kind": "preset", "key": preset})
        _save_user(request, preset=preset)
        return _home_logo_redirect()
    if preset == CUSTOM_KEY:
        branding = CardBranding.objects.filter(user=request.user).first() if request.user.is_authenticated else None
        if branding and branding.image:
            _save_session(request, {"kind": "upload", "path": branding.image.name})
            _save_user(request, preset="")
            return _home_logo_redirect()
        session = request.session.get(CARD_LOGO_SESSION) or {}
        if session.get("kind") == "upload" and session.get("path"):
            _save_session(request, session)
            return _home_logo_redirect()
    uploaded = request.FILES.get("logo")
    if uploaded and _is_verified(request):
        branding = CardBranding.objects.filter(user=request.user).first()
        if branding and branding.image:
            branding.image.delete(save=False)
        prefix = request.user.id
        path = _store_upload(prefix, uploaded)
        if path:
            _save_session(request, {"kind": "upload", "path": path})
            _save_user(request, preset="", image_path=path)
            return _home_logo_redirect()
    return redirect("home")
