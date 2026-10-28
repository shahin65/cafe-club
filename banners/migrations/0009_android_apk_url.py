from django.db import migrations

ANDROID_APK_URL = "https://cafeclub.amytisapp.ir/downloads/cafeclub.apk"


def set_android_apk(apps, schema_editor):
    SiteLink = apps.get_model("banners", "SiteLink")
    SiteLink.objects.filter(key="android").update(url=ANDROID_APK_URL)


def clear_android_apk(apps, schema_editor):
    SiteLink = apps.get_model("banners", "SiteLink")
    SiteLink.objects.filter(key="android").update(url="")


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0008_eventad"),
    ]

    operations = [
        migrations.RunPython(set_android_apk, clear_android_apk),
    ]
