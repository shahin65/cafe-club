import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_packages(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    rows = [
        ("coins_50", "۵۰ سکه", 50, 50000, 10),
        ("coins_150", "۱۵۰ سکه", 150, 100000, 20),
        ("coins_400", "۴۰۰ سکه", 400, 250000, 30),
    ]
    for sku, title, coins, price, order in rows:
        CoinPackage.objects.update_or_create(
            sku=sku,
            defaults={
                "title": title,
                "coins": coins,
                "price_toman": price,
                "sort_order": order,
                "is_active": True,
            },
        )


def unseed_packages(apps, schema_editor):
    CoinPackage = apps.get_model("banners", "CoinPackage")
    CoinPackage.objects.filter(sku__in=["coins_50", "coins_150", "coins_400"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("banners", "0023_venue_promo_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="coins",
            field=models.PositiveIntegerField(default=0, verbose_name="موجودی سکه"),
        ),
        migrations.CreateModel(
            name="CoinPackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku", models.SlugField(max_length=40, unique=True, verbose_name="شناسه محصول")),
                ("title", models.CharField(max_length=80, verbose_name="عنوان")),
                ("coins", models.PositiveIntegerField(verbose_name="تعداد سکه")),
                ("price_toman", models.PositiveIntegerField(verbose_name="قیمت تومان")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="ترتیب")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعال")),
            ],
            options={
                "verbose_name": "بسته سکه",
                "verbose_name_plural": "بسته‌های سکه",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gateway", models.CharField(choices=[("bitpay", "بیت‌پی"), ("bazaar", "کافه بازار"), ("myket", "مایکت")], db_index=True, max_length=12, verbose_name="درگاه")),
                ("source", models.CharField(blank=True, max_length=12, verbose_name="منبع ورود")),
                ("amount_toman", models.PositiveIntegerField(verbose_name="مبلغ تومان")),
                ("coins", models.PositiveIntegerField(verbose_name="سکه")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "در انتظار"), ("completed", "تکمیل‌شده"), ("failed", "ناموفق")],
                        db_index=True,
                        default="pending",
                        max_length=12,
                        verbose_name="وضعیت",
                    ),
                ),
                ("bitpay_id_get", models.CharField(blank=True, db_index=True, max_length=40, verbose_name="شناسه بیت‌پی")),
                ("bitpay_trans_id", models.CharField(blank=True, max_length=40, verbose_name="تراکنش بیت‌پی")),
                ("purchase_token", models.CharField(blank=True, max_length=255, verbose_name="توکن خرید فروشگاه")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="پاسخ درگاه")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("completed_at", models.DateTimeField(blank=True, null=True, verbose_name="زمان تکمیل")),
                (
                    "package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="banners.coinpackage",
                        verbose_name="بسته",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="کاربر",
                    ),
                ),
            ],
            options={
                "verbose_name": "تراکنش پرداخت",
                "verbose_name_plural": "تراکنش‌های پرداخت",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="paymenttransaction",
            constraint=models.UniqueConstraint(
                condition=models.Q(("purchase_token", ""), _negated=True),
                fields=("gateway", "purchase_token"),
                name="unique_store_purchase_token",
            ),
        ),
        migrations.RunPython(seed_packages, unseed_packages),
    ]
