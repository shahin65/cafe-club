from pathlib import Path
from uuid import uuid4

from django.core.files.storage import default_storage
from django.shortcuts import redirect
from django.templatetags.static import static
from django.views.decorators.http import require_POST
from PIL import Image

from scenarios.models import CardBranding

CARD_LOGO_SESSION = "card_logo"
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
    if branding.image:
        return {"kind": "upload", "url": branding.image.url}
    if branding.preset in PRESETS:
        return {"kind": "preset", "key": branding.preset, "url": static(PRESETS[branding.preset])}
    return None


def _choice_from_session(data):
    data = data or {}
    if data.get("kind") == "upload" and data.get("path"):
        if default_storage.exists(data["path"]):
            return {"kind": "upload", "url": default_storage.url(data["path"])}
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


def _store_upload(prefix, upload):
    if not upload or upload.size > ICON_MAX:
        return None
    suffix = ICON_TYPES.get(Path(upload.name or "").suffix.lower())
    if not suffix:
        return None
    try:
        Image.open(upload).verify()
    except Exception:
        return None
    upload.seek(0)
    return default_storage.save(f"card_logos/{prefix}/{uuid4().hex}{suffix}", upload)


def _save_session(request, payload):
    request.session[CARD_LOGO_SESSION] = payload
    request.session.modified = True


def _save_user(request, preset="", image_path=""):
    if not request.user.is_authenticated:
        return
    branding, _created = CardBranding.objects.get_or_create(user=request.user)
    branding.preset = preset
    if image_path:
        branding.image = image_path
    else:
        branding.image = ""
    branding.save()


@require_POST
def save_card_logo(request):
    preset = (request.POST.get("preset") or "").strip()
    if preset in PRESETS:
        _save_session(request, {"kind": "preset", "key": preset})
        _save_user(request, preset=preset)
        return redirect("home")
    uploaded = request.FILES.get("logo")
    if uploaded:
        if not request.user.is_authenticated:
            request.session.save()
        prefix = request.user.id if request.user.is_authenticated else (request.session.session_key or "anon")
        path = _store_upload(prefix, uploaded)
        if path:
            _save_session(request, {"kind": "upload", "path": path})
            _save_user(request, image_path=path)
    return redirect("home")
