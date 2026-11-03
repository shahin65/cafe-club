from django.db import migrations, models


def seed_lab_packages(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    rows = [
        ("lab_bazaar_5k", "تست خرید کافه بازار", "bazaar", 5000, 900),
        ("lab_myket_5k", "تست خرید مایکت", "myket", 5000, 910),
    ]
    for sku, title, plan_key, price, order in rows:
        CoinPackage.objects.update_or_create(
            sku=sku,
            defaults={
                "title": title,
                "kind": "lab",
                "plan_key": plan_key,
                "price_toman": price,
                "sort_order": order,
                "is_active": True,
            },
        )


def drop_lab_packages(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    CoinPackage.objects.filter(sku__in=["lab_bazaar_5k", "lab_myket_5k"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0028_bazaar_refresh_token"),
    ]

    operations = [
        migrations.AlterField(
            model_name="coinpackage",
            name="kind",
            field=models.CharField(
                choices=[("ad", "پلن آگهی"), ("venue", "پلن کجا برم؟"), ("lab", "تست آزمایشگاه")],
                db_index=True,
                default="ad",
                max_length=12,
                verbose_name="نوع محصول",
            ),
        ),
        migrations.RunPython(seed_lab_packages, drop_lab_packages),
    ]
