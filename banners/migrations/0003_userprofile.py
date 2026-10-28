import random

from django.conf import settings
from django.db import migrations, models


def allocate_id(used):
    for _ in range(200):
        candidate = random.randint(100000, 999999)
        if candidate not in used:
            used.add(candidate)
            return candidate
    raise RuntimeError("شناسه جدیدی برای کاربر ساخته نشد.")


def create_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    UserProfile = apps.get_model("banners", "UserProfile")
    used = set(UserProfile.objects.values_list("public_id", flat=True))
    for user in User.objects.all():
        if UserProfile.objects.filter(user_id=user.pk).exists():
            continue
        UserProfile.objects.create(user=user, public_id=allocate_id(used))


def drop_profiles(apps, schema_editor):
    UserProfile = apps.get_model("banners", "UserProfile")
    UserProfile.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("banners", "0002_seed_banners"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.PositiveIntegerField(unique=True, verbose_name="شناسه شش‌رقمی")),
                ("is_verified", models.BooleanField(default=False, verbose_name="تیک آبی")),
                ("bio", models.CharField(blank=True, max_length=280, verbose_name="بیوگرافی")),
                ("photo", models.ImageField(blank=True, upload_to="profiles", verbose_name="عکس پروفایل")),
                ("google_email", models.EmailField(blank=True, max_length=254, null=True, unique=True, verbose_name="جیمیل متصل")),
                ("google_sub", models.CharField(blank=True, max_length=64, null=True, unique=True, verbose_name="شناسه گوگل")),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=models.CASCADE,
                        related_name="club_profile",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "تیک آبی",
                "verbose_name_plural": "تیک آبی",
                "ordering": ["public_id"],
            },
        ),
        migrations.RunPython(create_profiles, drop_profiles),
    ]
