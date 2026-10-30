from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0015_userprofile_display_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventad",
            name="event_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="زمان برگزاری"),
        ),
    ]
