from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.views.decorators.http import require_GET

from banners.app_source import persist_source, normalize_source


@require_GET
def favicon(request):
    path = settings.BASE_DIR / "static" / "favicon.ico"
    return HttpResponse(path.read_bytes(), content_type="image/x-icon")


@require_GET
def web_manifest(request):
    icon = request.build_absolute_uri(static("Logo.png"))
    return JsonResponse(
        {
            "id": "/",
            "name": "کافه کلاب",
            "short_name": "کافه کلاب",
            "description": "کافه کلاب",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#05060c",
            "theme_color": "#000000",
            "lang": "fa",
            "dir": "rtl",
            "icons": [
                {"src": icon, "sizes": "1024x1024", "type": "image/png", "purpose": "any"},
                {
                    "src": request.build_absolute_uri(static("pwa-192.png")),
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": request.build_absolute_uri(static("pwa-512.png")),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        }
    )


@require_GET
def service_worker(request):
    path = settings.BASE_DIR / "static" / "js" / "sw.js"
    response = FileResponse(path.open("rb"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


@require_GET
def install_page(request):
    if getattr(request, "app_source", ""):
        return redirect("home")
    return render(request, "banners/install.html")


@require_GET
def capture_app_source(request, source):
    source = normalize_source(source)
    if not source:
        raise Http404
    persist_source(request, source)
    return redirect("home")
