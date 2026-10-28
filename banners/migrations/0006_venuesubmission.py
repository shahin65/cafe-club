import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("banners", "0005_venues"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VenueSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, verbose_name="نام کلاب")),
                ("logo", models.ImageField(upload_to="venue_submissions/logos", verbose_name="لوگو")),
                ("photo_1", models.ImageField(blank=True, upload_to="venue_submissions/photos", verbose_name="تصویر ۱")),
                ("photo_2", models.ImageField(blank=True, upload_to="venue_submissions/photos", verbose_name="تصویر ۲")),
                ("photo_3", models.ImageField(blank=True, upload_to="venue_submissions/photos", verbose_name="تصویر ۳")),
                ("manager_name", models.CharField(max_length=80, verbose_name="نام مدیر یا سوپروایزر مجموعه")),
                ("address", models.CharField(max_length=300, verbose_name="آدرس")),
                ("phone", models.CharField(max_length=30, verbose_name="تلفن")),
                ("hours", models.CharField(max_length=200, verbose_name="روزها و ساعات کاری")),
                (
                    "city",
                    models.CharField(
                        blank=True,
                        help_text="برای ثبت نهایی در لیست، شهر را اینجا وارد کنید.",
                        max_length=80,
                        verbose_name="شهر",
                    ),
                ),
                ("is_reviewed", models.BooleanField(default=False, verbose_name="بررسی شده")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="venue_submissions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "درخواست ثبت کافه / کلاب",
                "verbose_name_plural": "درخواست‌های ثبت کافه و کلاب",
                "ordering": ["-created_at"],
            },
        ),
    ]
