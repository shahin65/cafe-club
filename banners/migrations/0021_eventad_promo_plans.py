from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0020_eventad_boost"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventad",
            name="latitude",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="عرض جغرافیایی"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="longitude",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name="طول جغرافیایی"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="pending_plan",
            field=models.CharField(blank=True, max_length=12, verbose_name="پلن در انتظار پرداخت"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="photo_1",
            field=models.ImageField(blank=True, upload_to="event_ads/gallery", verbose_name="تصویر اضافه ۱"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="photo_2",
            field=models.ImageField(blank=True, upload_to="event_ads/gallery", verbose_name="تصویر اضافه ۲"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="photo_3",
            field=models.ImageField(blank=True, upload_to="event_ads/gallery", verbose_name="تصویر اضافه ۳"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="promo_plan",
            field=models.CharField(blank=True, db_index=True, max_length=12, verbose_name="پلن تبلیغاتی"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="promo_rank",
            field=models.PositiveSmallIntegerField(db_index=True, default=0, verbose_name="رتبه پلن"),
        ),
        migrations.AddField(
            model_name="eventad",
            name="show_on_home",
            field=models.BooleanField(db_index=True, default=False, verbose_name="نمایش در صفحه اصلی"),
        ),
    ]
