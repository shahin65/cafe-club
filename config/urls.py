from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path
from django.views.decorators.http import require_GET

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
            "Disallow: /deal/",
            "Disallow: /staff/",
            f"Sitemap: {sitemap_url}",
            "",
        ]
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("robots.txt", robots_txt),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("staff/scenario-page-image/", upload_page_image, name="scenario_page_image"),
]

urlpatterns += i18n_patterns(
    path("", include("banners.urls")),
    path("", include("scenarios.urls")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
