import os
import sys

from django.apps import AppConfig


class BannersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "banners"
    verbose_name = "بنرها"

    def ready(self):
        from django.contrib import admin

        from . import signals  # noqa: F401

        admin.site.site_header = "پنل مدیریت کافه کلاب"
        admin.site.site_title = "مدیریت کافه کلاب"
        admin.site.index_title = "داشبورد مدیریت کافه کلاب"
        if "test" in sys.argv:
            return
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return
        script = os.path.basename(sys.argv[0] if sys.argv else "")
        if script in {"manage.py", "django-admin"} and "runserver" not in sys.argv:
            return
        from banners.telegram import start_poller as start_telegram_poller
        from banners.bale import start_poller as start_bale_poller

        start_telegram_poller()
        start_bale_poller()
