from django.db import migrations


def seed_policies(apps, schema_editor):
    ReviewPolicy = apps.get_model("assistant", "ReviewPolicy")
    from assistant.defaults import DEFAULTS

    for scope, data in DEFAULTS.items():
        ReviewPolicy.objects.get_or_create(
            scope=scope,
            defaults={
                "instructions": data["instructions"],
                "allowed_actions": data["allowed_actions"],
                "auto_reply_enabled": data.get("auto_reply_enabled", False),
                "auto_enabled": True,
                "confidence_threshold": "0.85",
            },
        )


def unseed_policies(apps, schema_editor):
    ReviewPolicy = apps.get_model("assistant", "ReviewPolicy")
    ReviewPolicy.objects.filter(scope__in=["comments", "ads", "venues", "ticks"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_policies, unseed_policies),
    ]
