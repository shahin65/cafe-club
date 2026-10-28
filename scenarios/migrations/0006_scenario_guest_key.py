from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scenarios", "0005_card_branding"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenario",
            name="guest_key",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="برای سناریوی دلخواه بدون حساب، به نشست مرورگر گره می‌خورد.",
                max_length=64,
                verbose_name="کلید مهمان",
            ),
        ),
    ]
