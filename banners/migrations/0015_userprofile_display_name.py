from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0014_sitesettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="display_name",
            field=models.CharField(
                blank=True,
                help_text="اگر پر شود، این نام به‌جای نام کاربری به خود کاربر و دیگران نشان داده می‌شود.",
                max_length=40,
                verbose_name="نام نمایشی",
            ),
        ),
    ]
