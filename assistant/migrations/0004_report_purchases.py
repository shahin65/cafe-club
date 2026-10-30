from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0003_schedule_realtime"),
    ]
    operations = [
        migrations.AddField(
            model_name="assistantconfig",
            name="report_purchases",
            field=models.BooleanField(default=True, verbose_name="گزارش خریدهای جدید به بله"),
        ),
    ]
