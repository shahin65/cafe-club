from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0019_tournament_stages"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventad",
            name="boost_channel",
            field=models.CharField(
                blank=True,
                help_text="برای اتصال بعدی درگاه بر اساس رفرال دایرکت، بازار یا مایکت.",
                max_length=12,
                verbose_name="منبع پرداخت نردبان",
            ),
        ),
        migrations.AddField(
            model_name="eventad",
            name="boost_requested",
            field=models.BooleanField(default=False, verbose_name="درخواست نردبان"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="boosted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="زمان نردبان"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="is_boosted",
            field=models.BooleanField(db_index=True, default=False, verbose_name="نردبان‌شده"),
        ),
    ]
