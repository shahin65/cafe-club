from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0029_lab_store_packages"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="mobile",
            field=models.CharField(
                blank=True,
                max_length=16,
                null=True,
                unique=True,
                verbose_name="موبایل تاییدشده",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="telegram_chat_id",
            field=models.CharField(
                blank=True,
                max_length=64,
                null=True,
                unique=True,
                verbose_name="شناسه چت تلگرام",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="bale_chat_id",
            field=models.CharField(
                blank=True,
                max_length=64,
                null=True,
                unique=True,
                verbose_name="شناسه چت بله",
            ),
        ),
    ]
