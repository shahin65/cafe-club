from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0033_paid_display_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="show_home_banners",
            field=models.BooleanField(
                default=False,
                help_text="پیش‌فرض خاموش است. با روشن کردن، بنرهای فعال در صفحه اول می‌چرخند.",
                verbose_name="اسلایدر بنر صفحه اول نمایش داده شود",
            ),
        ),
    ]
