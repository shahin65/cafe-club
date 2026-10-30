from django.db import migrations, models


def drop_coin_products(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    PaymentTransaction = apps.get_model("banners", "PaymentTransaction")
    PaymentTransaction.objects.filter(package__sku__in=["coins_50", "coins_150", "coins_400"]).delete()
    CoinPackage.objects.filter(sku__in=["coins_50", "coins_150", "coins_400"]).delete()
    CoinPackage.objects.filter(kind="coins").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0025_promo_skus"),
    ]

    operations = [
        migrations.RunPython(drop_coin_products, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="userprofile",
            name="coins",
        ),
        migrations.RemoveField(
            model_name="coinpackage",
            name="coins",
        ),
        migrations.RemoveField(
            model_name="paymenttransaction",
            name="coins",
        ),
        migrations.AlterField(
            model_name="coinpackage",
            name="kind",
            field=models.CharField(
                choices=[("ad", "پلن آگهی"), ("venue", "پلن کجا برم؟")],
                db_index=True,
                default="ad",
                max_length=12,
                verbose_name="نوع محصول",
            ),
        ),
    ]
