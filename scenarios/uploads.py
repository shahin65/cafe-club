from pathlib import Path
from uuid import uuid4

from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from PIL import Image

ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
MAX_BYTES = 4 * 1024 * 1024


@staff_member_required
@require_POST
def upload_page_image(request):
    upload = request.FILES.get("upload")
    if not upload:
        return JsonResponse({"uploaded": 0, "error": {"message": "فایل تصویر را انتخاب کنید."}}, status=400)
    if upload.size > MAX_BYTES:
        return JsonResponse({"uploaded": 0, "error": {"message": "حجم تصویر نباید بیشتر از ۴ مگابایت باشد."}}, status=400)
    suffix = ALLOWED_TYPES.get(upload.content_type)
    if not suffix:
        name = Path(upload.name or "").suffix.lower()
        suffix = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png", ".gif": ".gif", ".webp": ".webp"}.get(name)
    if not suffix:
        return JsonResponse({"uploaded": 0, "error": {"message": "فقط تصویر JPG، PNG، GIF یا WebP مجاز است."}}, status=400)
    try:
        Image.open(upload).verify()
    except Exception:
        return JsonResponse({"uploaded": 0, "error": {"message": "فایل انتخاب‌شده یک تصویر معتبر نیست."}}, status=400)
    upload.seek(0)
    filename = f"scenario_pages/{uuid4().hex}{suffix}"
    saved = default_storage.save(filename, upload)
    url = request.build_absolute_uri(default_storage.url(saved))
    return JsonResponse({"uploaded": 1, "fileName": Path(saved).name, "url": url})
