from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path
from django.views.decorators.http import require_GET

from banners import messenger_views, pwa_views
from scenarios.sitemaps import SITEMAPS
from scenarios.uploads import upload_page_image


@require_GET
def robots_txt(request):
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /dev-lab/",
            "Disallow: /deal/",
            "Disallow: /staff/",
            "Disallow: /account/",
            "Disallow: /my-scenarios/",
            f"Sitemap: {sitemap_url}",
            "",
        ]
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


urlpatterns = [
    path("admin/ai-assistant/", include("assistant.urls")),
    path("admin/", admin.site.urls),
    path("auth/telegram/webhook/", messenger_views.telegram_webhook, name="telegram_webhook"),
    path(
        "auth/telegram/webhook/<str:secret>/",
        messenger_views.telegram_webhook,
        name="telegram_webhook_legacy",
    ),
    path("auth/bale/webhook/<str:secret>/", messenger_views.bale_webhook, name="bale_webhook"),
    path("favicon.ico", pwa_views.favicon, name="favicon"),
    path("manifest.webmanifest", pwa_views.web_manifest, name="web_manifest"),
    path("sw.js", pwa_views.service_worker, name="service_worker"),
    path("robots.txt", robots_txt),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("staff/scenario-page-image/", upload_page_image, name="scenario_page_image"),
    path("app/<slug:source>/", pwa_views.capture_app_source, name="app_source"),
]

urlpatterns += [
    path("", include("banners.urls")),
    path("", include("scenarios.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
