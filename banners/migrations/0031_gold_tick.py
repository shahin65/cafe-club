from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0030_messenger_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="is_gold_verified",
            field=models.BooleanField("تیک طلایی", default=False),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="is_verified",
            field=models.BooleanField(
                "تیک آبی",
                default=False,
                help_text="پس از ثبت‌نام با شماره در تلگرام یا بله به‌صورت خودکار فعال می‌شود.",
            ),
        ),
        migrations.AlterModelOptions(
            name="userprofile",
            options={"ordering": ["public_id"], "verbose_name": "پروفایل کاربر", "verbose_name_plural": "پروفایل کاربران"},
        ),
        migrations.AlterModelOptions(
            name="bluetickrequest",
            options={
                "ordering": ["-created_at"],
                "verbose_name": "درخواست تیک طلایی",
                "verbose_name_plural": "درخواست‌های تیک طلایی",
            },
        ),
    ]
