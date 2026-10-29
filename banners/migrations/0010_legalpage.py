from django.db import migrations, models


def seed_legal_pages(apps, schema_editor):
    LegalPage = apps.get_model("banners", "LegalPage")
    LegalPage.objects.get_or_create(
        key="privacy",
        defaults={
            "title": "سیاست حفظ حریم خصوصی",
            "title_en": "Privacy Policy",
            "body": (
                "کافه کلاب اطلاعات حساب، شناسه کاربری و در صورت اتصال جیمیل، نشانی ایمیل را برای ارائه خدمات برنامه نگه می‌دارد. "
                "نظرها، امتیازها، آگهی‌ها و درخواست‌های ارسال‌شده توسط کاربر برای بررسی و نمایش ذخیره می‌شوند. "
                "این اطلاعات به اشخاص ثالث فروخته نمی‌شود و فقط برای کارکرد برنامه، پشتیبانی و امنیت استفاده می‌گردد. "
                "می‌توانید متن این صفحه را از پنل مدیریت به‌روز کنید."
            ),
            "body_en": (
                "Cafe Club stores account details, the public user ID, and Gmail address when connected, "
                "so the app can work. Comments, ratings, ads, and submitted forms are kept for review and display. "
                "This information is not sold to third parties. You can update this page in the admin panel."
            ),
        },
    )
    LegalPage.objects.get_or_create(
        key="terms",
        defaults={
            "title": "شرایط استفاده از خدمات",
            "title_en": "Terms of Service",
            "body": (
                "استفاده از کافه کلاب به معنی پذیرش این شرایط است. کاربر مسئول محتوای آگهی، نظر، سناریو و اطلاعات ارسالی خود است. "
                "محتوای نامناسب، خلاف قانون یا گمراه‌کننده ممکن است حذف شود و دسترسی محدود گردد. "
                "خدمات ممکن است تغییر کند یا موقتاً در دسترس نباشد. "
                "می‌توانید متن این صفحه را از پنل مدیریت به‌روز کنید."
            ),
            "body_en": (
                "Using Cafe Club means you accept these terms. You are responsible for ads, comments, scenarios, "
                "and other content you submit. Unlawful or misleading content may be removed. "
                "The service may change or be unavailable at times. You can update this page in the admin panel."
            ),
        },
    )


def unseed_legal_pages(apps, schema_editor):
    LegalPage = apps.get_model("banners", "LegalPage")
    LegalPage.objects.filter(key__in=["privacy", "terms"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0009_android_apk_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="LegalPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "key",
                    models.CharField(
                        choices=[("privacy", "سیاست حفظ حریم خصوصی"), ("terms", "شرایط استفاده از خدمات")],
                        max_length=20,
                        unique=True,
                        verbose_name="شناسه",
                    ),
                ),
                ("title", models.CharField(max_length=120, verbose_name="عنوان فارسی")),
                ("title_en", models.CharField(blank=True, max_length=120, verbose_name="عنوان انگلیسی")),
                ("body", models.TextField(blank=True, verbose_name="متن فارسی")),
                ("body_en", models.TextField(blank=True, verbose_name="متن انگلیسی")),
            ],
            options={
                "verbose_name": "صفحه حقوقی",
                "verbose_name_plural": "صفحات حقوقی",
                "ordering": ["key"],
            },
        ),
        migrations.RunPython(seed_legal_pages, unseed_legal_pages),
    ]
