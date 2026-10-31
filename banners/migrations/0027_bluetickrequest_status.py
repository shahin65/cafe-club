from django.db import migrations, models


def fill_status(apps, schema_editor):
    BlueTickRequest = apps.get_model("banners", "BlueTickRequest")
    UserProfile = apps.get_model("banners", "UserProfile")
    verified_ids = set(
        UserProfile.objects.filter(is_verified=True).values_list("user_id", flat=True)
    )
    for req in BlueTickRequest.objects.all().iterator():
        if not req.is_reviewed:
            status = "pending"
        elif req.user_id in verified_ids:
            status = "approved"
        else:
            status = "rejected"
        if req.status != status:
            req.status = status
            req.save(update_fields=["status"])


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0026_remove_coins"),
    ]

    operations = [
        migrations.AddField(
            model_name="bluetickrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "در انتظار بررسی"),
                    ("approved", "تأیید شده"),
                    ("rejected", "رد شده"),
                ],
                db_index=True,
                default="pending",
                max_length=12,
                verbose_name="نتیجه",
            ),
        ),
        migrations.RunPython(fill_status, migrations.RunPython.noop),
    ]
