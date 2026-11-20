"""Compress image/video uploads the same way Kill Box does before they leave the host."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-m4v",
}
IMAGE_MAX_BYTES = 8 * 1024 * 1024
VIDEO_MAX_BYTES = 40 * 1024 * 1024
VIDEO_MAX_SECONDS = 60


class MediaError(ValueError):
    pass


def public_media_url(name_or_field) -> str:
    from django.conf import settings
    from django.core.files.storage import default_storage

    name = getattr(name_or_field, "name", name_or_field) or ""
    if not name:
        return ""
    try:
        url = name_or_field.url if hasattr(name_or_field, "url") else default_storage.url(str(name))
    except ValueError:
        return ""
    if str(url).startswith(("http://", "https://")):
        return url
    domain = str(getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "") or "").strip()
    if getattr(settings, "ARVAN_MEDIA_ENABLED", False) and domain:
        return f"https://{domain}/{str(name).lstrip('/')}"
    return url


def classify(uploaded: UploadedFile) -> str:
    content_type = str(getattr(uploaded, "content_type", "") or "").lower()
    name = str(getattr(uploaded, "name", "") or "").lower()
    if content_type in IMAGE_TYPES or name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return "image"
    if content_type in VIDEO_TYPES or name.endswith((".mp4", ".webm", ".mov", ".m4v")):
        return "video"
    raise MediaError("فقط تصویر یا ویدیو پذیرفته می‌شود.")


def encode_still(stream, max_side: int = 1440, name: str = "media.webp") -> ContentFile:
    try:
        image = Image.open(stream)
        image = ImageOps.exif_transpose(image)
        if getattr(image, "n_frames", 1) > 1:
            image.seek(0)
        image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise MediaError("فایل تصویر قابل خواندن نبود.") from exc
    width, height = image.size
    if width < 4 or height < 4:
        raise MediaError("تصویر خیلی کوچک است.")
    scale = min(1.0, max_side / max(width, height))
    if scale < 1:
        image = image.resize(
            (round(width * scale), round(height * scale)),
            Image.Resampling.LANCZOS,
        )
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=78, method=6)
    return ContentFile(buffer.getvalue(), name=name)


def prepare_image(uploaded: UploadedFile, max_side: int = 1440, max_bytes: int = IMAGE_MAX_BYTES) -> ContentFile:
    size = getattr(uploaded, "size", 0) or 0
    if size > max_bytes:
        raise MediaError("حجم تصویر بیش از حد مجاز است.")
    if hasattr(uploaded, "seek"):
        uploaded.seek(0)
    return encode_still(uploaded, max_side=max_side, name="media.webp")


def find_ffmpeg() -> str:
    from django.conf import settings

    candidates = [
        str(getattr(settings, "FFMPEG_BIN", "") or "").strip(),
        shutil.which("ffmpeg") or "",
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/bin/ffmpeg",
        "/usr/local/ffmpeg/bin/ffmpeg",
    ]
    for path in candidates:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return ""


def mp4_duration_seconds(uploaded: UploadedFile) -> float | None:
    uploaded.seek(0)
    limit = min(int(getattr(uploaded, "size", 0) or 0), 4_000_000)
    data = uploaded.read(limit)
    uploaded.seek(0)
    idx = data.find(b"mvhd")
    if idx < 0 or idx + 32 > len(data):
        return None
    start = idx + 4
    version = data[start]
    try:
        if version == 0:
            timescale = int.from_bytes(data[start + 12 : start + 16], "big")
            duration = int.from_bytes(data[start + 16 : start + 20], "big")
        elif version == 1:
            timescale = int.from_bytes(data[start + 20 : start + 24], "big")
            duration = int.from_bytes(data[start + 24 : start + 32], "big")
        else:
            return None
    except Exception:
        return None
    if not timescale:
        return None
    return duration / timescale


def prepare_video(
    uploaded: UploadedFile,
    max_seconds: int = VIDEO_MAX_SECONDS,
    max_bytes: int = VIDEO_MAX_BYTES,
) -> ContentFile:
    size = getattr(uploaded, "size", 0) or 0
    if size > max_bytes:
        raise MediaError("حجم ویدیو بیش از حد مجاز است.")
    duration = mp4_duration_seconds(uploaded)
    if duration is not None and duration > max_seconds + 0.4:
        raise MediaError(f"مدت ویدیو نباید بیشتر از {max_seconds} ثانیه باشد.")
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        uploaded.seek(0)
        name = Path(getattr(uploaded, "name", "clip.mp4")).name
        return ContentFile(uploaded.read(), name=name or "clip.mp4")
    suffix = Path(getattr(uploaded, "name", "clip.mp4")).suffix or ".mp4"
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"in{suffix}"
        dest = Path(tmp) / "out.mp4"
        uploaded.seek(0)
        src.write_bytes(uploaded.read())
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-t",
            str(max_seconds),
            "-vf",
            "scale='min(1280,iw)':-2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(dest),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=90)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            raise MediaError("بهینه‌سازی ویدیو ناموفق بود.") from exc
        return ContentFile(dest.read_bytes(), name="clip.mp4")


def prepare_upload(
    uploaded: UploadedFile,
    *,
    max_side: int = 1440,
    max_image_bytes: int = IMAGE_MAX_BYTES,
    max_video_bytes: int = VIDEO_MAX_BYTES,
    max_seconds: int = VIDEO_MAX_SECONDS,
    images_only: bool = False,
) -> ContentFile:
    kind = classify(uploaded)
    if kind == "image":
        return prepare_image(uploaded, max_side=max_side, max_bytes=max_image_bytes)
    if images_only:
        raise MediaError("فقط تصویر JPG، PNG، GIF یا WebP مجاز است.")
    return prepare_video(uploaded, max_seconds=max_seconds, max_bytes=max_video_bytes)
