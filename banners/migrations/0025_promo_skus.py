from django.db import migrations, models
import django.db.models.deletion


def seed_catalog(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    CoinPackage.objects.filter(kind="").update(kind="coins")
    CoinPackage.objects.filter(sku__in=["coins_50", "coins_150", "coins_400"]).update(kind="coins")
    rows = [
        ("ad_bronze", "پلن آگهی برنزی", "ad", "bronze", 0, 100000, 40),
        ("ad_silver", "پلن آگهی نقره‌ای", "ad", "silver", 0, 200000, 50),
        ("ad_gold", "پلن آگهی طلایی", "ad", "gold", 0, 250000, 60),
        ("venue_bronze", "پلن کافه برنزی", "venue", "bronze", 0, 250000, 70),
        ("venue_silver", "پلن کافه نقره‌ای", "venue", "silver", 0, 450000, 80),
        ("venue_gold", "پلن کافه طلایی", "venue", "gold", 0, 800000, 90),
    ]
    for sku, title, kind, plan_key, coins, price, order in rows:
        CoinPackage.objects.update_or_create(
            sku=sku,
            defaults={
                "title": title,
                "kind": kind,
                "plan_key": plan_key,
                "coins": coins,
                "price_toman": price,
                "sort_order": order,
                "is_active": True,
            },
        )


def unseed_catalog(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    CoinPackage.objects.filter(sku__in=["ad_bronze", "ad_silver", "ad_gold", "venue_bronze", "venue_silver", "venue_gold"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0024_coin_payments"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="coinpackage",
            options={"ordering": ["kind", "sort_order", "id"], "verbose_name": "محصول درون‌برنامه‌ای", "verbose_name_plural": "محصولات درون‌برنامه‌ای و SKU"},
        ),
        migrations.AddField(
            model_name="coinpackage",
            name="kind",
            field=models.CharField(
                choices=[("coins", "بسته سکه"), ("ad", "پلن آگهی"), ("venue", "پلن کجا برم؟")],
                db_index=True,
                default="coins",
                max_length=12,
                verbose_name="نوع محصول",
            ),
        ),
        migrations.AddField(
            model_name="coinpackage",
            name="plan_key",
            field=models.CharField(blank=True, max_length=12, verbose_name="کلید پلن"),
        ),
        migrations.AlterField(
            model_name="coinpackage",
            name="coins",
            field=models.PositiveIntegerField(default=0, verbose_name="تعداد سکه"),
        ),
        migrations.AlterField(
            model_name="coinpackage",
            name="sku",
            field=models.SlugField(max_length=40, unique=True, verbose_name="شناسه محصول (SKU)"),
        ),
        migrations.AddField(
            model_name="paymenttransaction",
            name="event_ad",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payments",
                to="banners.eventad",
                verbose_name="آگهی",
            ),
        ),
        migrations.AddField(
            model_name="paymenttransaction",
            name="venue",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payments",
                to="banners.venue",
                verbose_name="کافه / کلاب",
            ),
        ),
        migrations.AlterField(
            model_name="paymenttransaction",
            name="coins",
            field=models.PositiveIntegerField(default=0, verbose_name="سکه"),
        ),
        migrations.AlterField(
            model_name="paymenttransaction",
            name="package",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments",
                to="banners.coinpackage",
                verbose_name="محصول",
            ),
        ),
        migrations.RunPython(seed_catalog, unseed_catalog),
    ]
