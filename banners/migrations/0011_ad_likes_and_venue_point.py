from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("banners", "0010_legalpage"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventad",
            name="city",
            field=models.CharField(default="", max_length=80, verbose_name="شهر"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="district",
            field=models.CharField(default="", max_length=120, verbose_name="محدوده"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="scenario",
            field=models.CharField(default="", max_length=120, verbose_name="سناریو"),
        ),
        migrations.AddField(
            model_name="venuesubmission",
            name="latitude",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="عرض جغرافیایی"),
        ),
        migrations.AddField(
            model_name="venuesubmission",
            name="longitude",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="طول جغرافیایی"),
        ),
        migrations.CreateModel(
            name="EventAdLike",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guest_key", models.CharField(blank=True, max_length=64, verbose_name="کلید مهمان")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان")),
                (
                    "ad",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="likes",
                        to="banners.eventad",
                        verbose_name="آگهی",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_ad_likes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "لایک آگهی",
                "verbose_name_plural": "لایک‌های آگهی",
            },
        ),
    ]
