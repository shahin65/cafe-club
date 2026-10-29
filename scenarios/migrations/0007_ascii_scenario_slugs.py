from django.db import migrations, models
from django.utils.text import slugify


def ascii_scenario_slugs(apps, schema_editor):
    Scenario = apps.get_model("scenarios", "Scenario")
    used = set()
    for scenario in Scenario.objects.order_by("id"):
        suggested = (scenario.slug or "").strip()
        if suggested and not suggested.isascii():
            suggested = ""
        base = slugify(suggested, allow_unicode=False) or slugify(scenario.name or "", allow_unicode=False)
        if not base:
            base = f"scenario-{scenario.pk}"
        slug = base[:80]
        index = 2
        while slug in used:
            suffix = f"-{index}"
            slug = f"{base[: max(1, 80 - len(suffix))]}{suffix}"
            index += 1
        used.add(slug)
        if scenario.slug != slug:
            scenario.slug = slug
            scenario.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("scenarios", "0006_scenario_guest_key"),
    ]

    operations = [
        migrations.RunPython(ascii_scenario_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="scenario",
            name="slug",
            field=models.SlugField(
                allow_unicode=False,
                blank=True,
                help_text="شناسه لاتین داخلی. نشانی صفحات رول‌بوک و قوانین با شماره سناریو است تا روی هاست خطای Not Found ندهد.",
                max_length=80,
                unique=True,
                verbose_name="نامک آدرس",
            ),
        ),
    ]
