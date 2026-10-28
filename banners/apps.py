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
