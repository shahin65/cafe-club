from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0022_venue_public_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="venue",
            name="boost_channel",
            field=models.CharField(blank=True, max_length=12, verbose_name="منبع پرداخت نردبان"),
        ),
        migrations.AddField(
            model_name="venue",
            name="boost_requested",
            field=models.BooleanField(default=False, verbose_name="درخواست نردبان"),
        ),
        migrations.AddField(
            model_name="venue",
            name="boosted_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="زمان نردبان"),
        ),
        migrations.AddField(
            model_name="venue",
            name="pending_plan",
            field=models.CharField(blank=True, max_length=12, verbose_name="پلن در انتظار پرداخت"),
        ),
        migrations.AddField(
            model_name="venue",
            name="promo_expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="پایان پلن تبلیغاتی"),
        ),
        migrations.AddField(
            model_name="venue",
            name="promo_plan",
            field=models.CharField(blank=True, db_index=True, max_length=12, verbose_name="پلن تبلیغاتی"),
        ),
        migrations.AddField(
            model_name="venue",
            name="promo_rank",
            field=models.PositiveSmallIntegerField(db_index=True, default=0, verbose_name="رتبه پلن"),
        ),
        migrations.AddField(
            model_name="venue",
            name="show_on_home",
            field=models.BooleanField(db_index=True, default=False, verbose_name="نمایش در صفحه اصلی"),
        ),
    ]
