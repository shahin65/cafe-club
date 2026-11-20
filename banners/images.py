from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from banners.media import MediaError, prepare_image, prepare_upload

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
AD_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_EDGE = 512
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def optimize_image(upload, max_edge=MAX_EDGE, max_bytes=MAX_UPLOAD_BYTES):
    try:
        content = prepare_image(upload, max_side=max_edge, max_bytes=max_bytes)
    except MediaError as exc:
        raise ValidationError(str(exc)) from exc
    content.seek(0)
    return ContentFile(content.read(), name=f"{uuid4().hex}.webp")


def optimize_profile_photo(upload):
    return optimize_image(upload, max_edge=MAX_EDGE)


def optimize_venue_image(upload, max_edge=1200):
    return optimize_image(upload, max_edge=max_edge)


def optimize_ad_image(upload, max_edge=1200):
    return optimize_image(upload, max_edge=max_edge, max_bytes=AD_UPLOAD_BYTES)


def optimize_upload(upload, *, max_edge=1440, images_only=False):
    try:
        content = prepare_upload(upload, max_side=max_edge, images_only=images_only)
    except MediaError as exc:
        raise ValidationError(str(exc)) from exc
    content.seek(0)
    name = content.name or "media.webp"
    return ContentFile(content.read(), name=name)
