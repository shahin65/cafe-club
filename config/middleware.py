from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class ForceAdminPersianMiddleware(MiddlewareMixin):
    """Keep the administration panel in Persian even if the public site is English."""

    def process_request(self, request):
        path = request.path
        if path == "/admin" or path.startswith("/admin/"):
            translation.activate("fa")
            request.LANGUAGE_CODE = "fa"
