from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scenarios", "0007_ascii_scenario_slugs"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenario",
            name="play_count",
            field=models.PositiveIntegerField(default=0, editable=False, verbose_name="تعداد بازی"),
        ),
    ]
