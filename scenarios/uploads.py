from pathlib import Path
from uuid import uuid4

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from banners.images import optimize_upload
from banners.media import public_media_url

MAX_BYTES = 4 * 1024 * 1024


@staff_member_required
@require_POST
def upload_page_image(request):
    upload = request.FILES.get("upload")
    if not upload:
        return JsonResponse({"uploaded": 0, "error": {"message": "فایل تصویر را انتخاب کنید."}}, status=400)
    if upload.size > MAX_BYTES:
        return JsonResponse({"uploaded": 0, "error": {"message": "حجم تصویر نباید بیشتر از ۴ مگابایت باشد."}}, status=400)
    try:
        stored = optimize_upload(upload, max_edge=1440, images_only=True)
    except ValidationError as exc:
        message = " ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
        return JsonResponse({"uploaded": 0, "error": {"message": message}}, status=400)
    filename = f"scenario_pages/{uuid4().hex}.webp"
    saved = default_storage.save(filename, stored)
    url = public_media_url(saved) or default_storage.url(saved)
    if not str(url).startswith(("http://", "https://")):
        url = request.build_absolute_uri(url)
    return JsonResponse({"uploaded": 1, "fileName": Path(saved).name, "url": url})
