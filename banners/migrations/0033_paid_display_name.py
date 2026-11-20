from django.db import migrations, models


def deactivate_rename_package(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    CoinPackage.objects.filter(sku="rename_50k").update(is_active=False)


def reactivate_rename_package(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    CoinPackage.objects.filter(sku="rename_50k").update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0032_staff_and_rename"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="paid_display_name_edit",
            field=models.BooleanField(
                default=False,
                help_text="اگر خاموش باشد تغییر دوباره نام نمایشی رایگان است. با روشن کردن، پرداخت ۵۰٬۰۰۰ تومانی از درگاه بازار، مایکت یا بیت‌پی فعال می‌شود.",
                verbose_name="ویرایش دوم نام نمایشی پولی باشد",
            ),
        ),
        migrations.RunPython(deactivate_rename_package, reactivate_rename_package),
    ]
