from django.db import migrations, models

import assistant.models


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0002_seed_review_policies"),
    ]

    operations = [
        migrations.AddField(
            model_name="assistantconfig",
            name="report_hours",
            field=models.JSONField(blank=True, default=assistant.models.default_report_hours, verbose_name="ساعات ارسال گزارش"),
        ),
        migrations.AddField(
            model_name="assistantconfig",
            name="review_hours",
            field=models.JSONField(blank=True, default=assistant.models.default_review_hours, verbose_name="ساعات بازبینی"),
        ),
        migrations.AddField(
            model_name="reviewpolicy",
            name="realtime_report",
            field=models.BooleanField(default=False, verbose_name="گزارش بلادرنگ به بله"),
        ),
        migrations.AddField(
            model_name="reviewpolicy",
            name="realtime_review",
            field=models.BooleanField(default=False, verbose_name="رسیدگی بلادرنگ"),
        ),
    ]
