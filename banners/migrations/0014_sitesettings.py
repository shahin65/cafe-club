from django.db import migrations, models


def create_settings(apps, schema_editor):
    SiteSettings = apps.get_model("banners", "SiteSettings")
    SiteSettings.objects.get_or_create(pk=1, defaults={"maintenance_mode": False})


def drop_settings(apps, schema_editor):
    SiteSettings = apps.get_model("banners", "SiteSettings")
    SiteSettings.objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0013_userprofile_app_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "maintenance_mode",
                    models.BooleanField(
                        default=False,
                        help_text="اگر فعال باشد سایت برای کاربران عادی بسته می‌شود تا زمان به‌روزرسانی.",
                        verbose_name="اپلیکیشن در دست تعمیر است",
                    ),
                ),
            ],
            options={
                "verbose_name": "وضعیت سایت",
                "verbose_name_plural": "وضعیت سایت",
            },
        ),
        migrations.RunPython(create_settings, drop_settings),
    ]
