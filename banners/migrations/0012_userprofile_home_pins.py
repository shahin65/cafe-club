from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0011_ad_likes_and_venue_point"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="home_scenario_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="حداکثر ۶ سناریوی پین‌شده برای بخش تقسیم نقش سریع.",
                verbose_name="سناریوهای صفحه اصلی",
            ),
        ),
    ]
