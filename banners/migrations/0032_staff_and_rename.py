from django.db import migrations, models


def seed_rename_package(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    CoinPackage.objects.update_or_create(
        sku="rename_50k",
        defaults={
            "title": "ویرایش نام نمایشی",
            "kind": "profile",
            "plan_key": "rename",
            "price_toman": 50000,
            "sort_order": 50,
            "is_active": True,
        },
    )


def unseed_rename_package(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    CoinPackage.objects.filter(sku="rename_50k").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0031_gold_tick"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="display_name_changes",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="بار اول رایگان است. از بار دوم به بعد مشمول هزینه می‌شود.",
                verbose_name="تعداد ویرایش نام نمایشی",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_manage_quick",
            field=models.BooleanField(
                default=False,
                help_text="ادمین می‌تواند سناریوهای تقسیم نقش سریع را از داخل سایت اضافه، ویرایش یا حذف کند.",
                verbose_name="ویرایش تقسیم نقش سریع",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_manage_large",
            field=models.BooleanField(
                default=False,
                help_text="ادمین می‌تواند تقسیم نقش سناریو تعداد بالا را از داخل سایت ویرایش و تکمیل کند.",
                verbose_name="ویرایش سناریو تعداد بالا",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_rulebook",
            field=models.BooleanField(
                default=False,
                help_text="ادمین می‌تواند متن رول‌بوک سناریوها را از داخل سایت ویرایش کند.",
                verbose_name="ویرایش رول‌بوک",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_rules",
            field=models.BooleanField(
                default=False,
                help_text="ادمین می‌تواند متن قوانین سناریوها را از داخل سایت ویرایش کند.",
                verbose_name="ویرایش قوانین",
            ),
        ),
        migrations.AlterField(
            model_name="coinpackage",
            name="kind",
            field=models.CharField(
                choices=[
                    ("ad", "پلن آگهی"),
                    ("venue", "پلن کجا برم؟"),
                    ("lab", "تست آزمایشگاه"),
                    ("profile", "پروفایل"),
                ],
                db_index=True,
                default="ad",
                max_length=12,
                verbose_name="نوع محصول",
            ),
        ),
        migrations.RunPython(seed_rename_package, unseed_rename_package),
    ]
