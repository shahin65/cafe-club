from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("banners", "0003_userprofile"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlueTickRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=80, verbose_name="نام و نام خانوادگی")),
                ("phone", models.CharField(max_length=20, verbose_name="شماره تماس")),
                ("biography", models.TextField(verbose_name="بیوگرافی")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")),
                ("is_reviewed", models.BooleanField(default=False, verbose_name="بررسی شده")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="blue_tick_requests",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "درخواست تیک آبی",
                "verbose_name_plural": "درخواست‌های تیک آبی",
                "ordering": ["-created_at"],
            },
        ),
    ]
