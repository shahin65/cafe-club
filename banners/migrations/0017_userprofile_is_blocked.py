from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0016_eventad_event_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="is_blocked",
            field=models.BooleanField(
                default=False,
                help_text="اگر فعال باشد این کاربر نمی‌تواند دوباره وارد حساب شود.",
                verbose_name="مسدود",
            ),
        ),
    ]
