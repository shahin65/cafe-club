from django.db import migrations, models


def seed_site_links(apps, schema_editor):
    SiteLink = apps.get_model("banners", "SiteLink")
    rows = [
        ("download", "android", "دانلود مستقیم اپلیکیشن اندروید", "Direct Android app download", 1),
        ("download", "ios", "دانلود مستقیم نسخه آیفون", "Direct iPhone download", 2),
        ("download", "bazaar", "دانلود نسخه کافه بازار", "Cafe Bazaar download", 3),
        ("download", "myket", "دانلود نسخه مایکت", "Myket download", 4),
        ("social", "instagram", "اینستاگرام", "Instagram", 1),
        ("social", "telegram", "تلگرام", "Telegram", 2),
        ("social", "whatsapp", "واتس‌اپ", "WhatsApp", 3),
        ("social", "rubika", "روبیکا", "Rubika", 4),
    ]
    for group, key, title, title_en, order in rows:
        SiteLink.objects.get_or_create(
            key=key,
            defaults={
                "group": group,
                "title": title,
                "title_en": title_en,
                "sort_order": order,
                "is_active": True,
            },
        )


def unseed_site_links(apps, schema_editor):
    SiteLink = apps.get_model("banners", "SiteLink")
    SiteLink.objects.filter(
        key__in=["android", "ios", "bazaar", "myket", "instagram", "telegram", "whatsapp", "rubika"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("banners", "0006_venuesubmission"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "group",
                    models.CharField(
                        choices=[("download", "دانلود اپلیکیشن"), ("social", "شبکه‌های اجتماعی")],
                        max_length=20,
                        verbose_name="گروه",
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        choices=[
                            ("android", "اندروید"),
                            ("ios", "آیفون"),
                            ("bazaar", "کافه بازار"),
                            ("myket", "مایکت"),
                            ("instagram", "اینستاگرام"),
                            ("telegram", "تلگرام"),
                            ("whatsapp", "واتس‌اپ"),
                            ("rubika", "روبیکا"),
                        ],
                        max_length=20,
                        unique=True,
                        verbose_name="شناسه",
                    ),
                ),
                ("title", models.CharField(max_length=80, verbose_name="عنوان فارسی")),
                ("title_en", models.CharField(blank=True, max_length=80, verbose_name="عنوان انگلیسی")),
                (
                    "url",
                    models.URLField(blank=True, help_text="اگر خالی باشد در صفحه تنظیمات نشان داده نمی‌شود.", verbose_name="لینک"),
                ),
                ("image", models.ImageField(blank=True, upload_to="site_links", verbose_name="آیکون / تصویر")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="ترتیب")),
            ],
            options={
                "verbose_name": "تنظیم",
                "verbose_name_plural": "تنظیمات",
                "ordering": ["group", "sort_order", "id"],
            },
        ),
        migrations.RunPython(seed_site_links, unseed_site_links),
    ]
