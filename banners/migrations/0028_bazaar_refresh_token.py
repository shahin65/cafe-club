from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0027_bluetickrequest_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="bazaar_refresh_token",
            field=models.TextField(blank=True),
        ),
    ]
