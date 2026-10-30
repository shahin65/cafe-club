import random

from django.db import migrations, models


def allocate_id(used):
    for _ in range(400):
        candidate = random.randint(100000, 999999)
        if candidate not in used:
            used.add(candidate)
            return candidate
    raise RuntimeError("شناسه جدیدی برای کافه ساخته نشد.")


def fill_venue_ids(apps, schema_editor):
    Venue = apps.get_model("banners", "Venue")
    used = set(Venue.objects.exclude(public_id=None).values_list("public_id", flat=True))
    for venue in Venue.objects.filter(public_id__isnull=True).order_by("id"):
        venue.public_id = allocate_id(used)
        venue.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0021_eventad_promo_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="venue",
            name="public_id",
            field=models.PositiveIntegerField(
                db_index=True,
                null=True,
                unique=True,
                verbose_name="شناسه شش‌رقمی",
            ),
        ),
        migrations.RunPython(fill_venue_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="venue",
            name="public_id",
            field=models.PositiveIntegerField(
                db_index=True,
                unique=True,
                verbose_name="شناسه شش‌رقمی",
            ),
        ),
    ]
