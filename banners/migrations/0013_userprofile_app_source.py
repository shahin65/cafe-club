from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0012_userprofile_home_pins"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="app_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "وب / نامشخص"),
                    ("direct", "نسخه دایرکت"),
                    ("bazaar", "کافه بازار"),
                    ("myket", "مایکت"),
                ],
                default="",
                help_text="اگر کاربر از لینک رفرال نسخه دایرکت، بازار یا مایکت وارد شده باشد اینجا ثبت می‌شود.",
                max_length=12,
                verbose_name="منبع اپلیکیشن",
            ),
        ),
    ]
