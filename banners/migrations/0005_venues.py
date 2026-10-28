import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("banners", "0004_bluetickrequest"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Venue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, verbose_name="اسم کلاب")),
                ("city", models.CharField(db_index=True, max_length=80, verbose_name="شهر")),
                ("logo", models.ImageField(blank=True, upload_to="venues/logos", verbose_name="لوگو")),
                ("manager_name", models.CharField(blank=True, max_length=80, verbose_name="نام مدیر یا سوپروایزر")),
                ("photo_1", models.ImageField(blank=True, upload_to="venues/photos", verbose_name="تصویر ۱")),
                ("photo_2", models.ImageField(blank=True, upload_to="venues/photos", verbose_name="تصویر ۲")),
                ("photo_3", models.ImageField(blank=True, upload_to="venues/photos", verbose_name="تصویر ۳")),
                (
                    "hours",
                    models.CharField(
                        blank=True,
                        help_text="نمونه: شنبه تا چهارشنبه ۱۶ تا ۲۴",
                        max_length=200,
                        verbose_name="روزها و ساعات کاری",
                    ),
                ),
                ("address", models.CharField(max_length=300, verbose_name="آدرس")),
                ("phone", models.CharField(blank=True, max_length=30, verbose_name="تلفن تماس")),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="عرض جغرافیایی")),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="طول جغرافیایی")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ثبت")),
            ],
            options={
                "verbose_name": "کافه / کلاب",
                "verbose_name_plural": "کافه‌ها و کلاب‌ها",
                "ordering": ["city", "name"],
            },
        ),
        migrations.CreateModel(
            name="VenueComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("author_name", models.CharField(max_length=40, verbose_name="نام")),
                ("body", models.TextField(max_length=1000, verbose_name="نظر")),
                ("is_approved", models.BooleanField(default=False, verbose_name="تأیید شده")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")),
                (
                    "venue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="banners.venue",
                        verbose_name="کافه / کلاب",
                    ),
                ),
            ],
            options={
                "verbose_name": "نظر کافه / کلاب",
                "verbose_name_plural": "نظرات کاربران در رابطه با کافه کلاب‌ها",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="VenueRating",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guest_key", models.CharField(blank=True, max_length=64, verbose_name="کلید مهمان")),
                ("stars", models.PositiveSmallIntegerField(verbose_name="امتیاز")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="به‌روزرسانی")),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="venue_ratings",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
                (
                    "venue",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ratings",
                        to="banners.venue",
                        verbose_name="کافه / کلاب",
                    ),
                ),
            ],
            options={
                "verbose_name": "امتیاز کافه",
                "verbose_name_plural": "امتیازهای کافه",
            },
        ),
        migrations.AddConstraint(
            model_name="venuerating",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", False)),
                fields=("venue", "user"),
                name="unique_venue_rating_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="venuerating",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", True)),
                fields=("venue", "guest_key"),
                name="unique_venue_rating_guest",
            ),
        ),
    ]
