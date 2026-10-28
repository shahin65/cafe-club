from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
AD_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_EDGE = 512
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def optimize_image(upload, max_edge=MAX_EDGE):
    if getattr(upload, "size", 0) > MAX_UPLOAD_BYTES:
        raise ValidationError("حجم تصویر نباید بیشتر از ۴ مگابایت باشد.")
    suffix = Path(getattr(upload, "name", "") or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValidationError("فقط تصویر JPG، PNG، GIF یا WebP مجاز است.")
    try:
        image = Image.open(upload)
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
    except Exception as exc:
        raise ValidationError("فایل انتخاب‌شده یک تصویر معتبر نیست.") from exc
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=80, method=6, optimize=True)
    buffer.seek(0)
    return ContentFile(buffer.read(), name=f"{uuid4().hex}.webp")


def optimize_profile_photo(upload):
    return optimize_image(upload, max_edge=MAX_EDGE)


def optimize_venue_image(upload, max_edge=1200):
    return optimize_image(upload, max_edge=max_edge)


def optimize_ad_image(upload, max_edge=1200):
    if getattr(upload, "size", 0) > AD_UPLOAD_BYTES:
        raise ValidationError("حجم تصویر آگهی نباید بیشتر از ۲ مگابایت باشد.")
    return optimize_image(upload, max_edge=max_edge)
