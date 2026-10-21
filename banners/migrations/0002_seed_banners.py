from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import migrations

SEED = [
    {
        "filename": "Banner1.webp",
        "title_fa": "شب‌های مرموز کافه کلاب",
        "title_en": "Mysterious Nights at Cafe Club",
        "description_fa": "باران، نور چراغ‌ها و شهری که رازهایش را فقط سر میز بازی لو می‌دهد. به شب‌های نقش‌آفرینی و استنتاج کافه کلاب بپیوندید.",
        "description_en": "Rain, lamplight, and a city that only gives up its secrets at the game table. Join Cafe Club’s nights of roleplay and deduction.",
        "external_url": "",
        "internal_url": "/nights/",
        "is_active": True,
        "display_order": 1,
    },
    {
        "filename": "Banner2.webp",
        "title_fa": "ایستگاه بازی کنسول",
        "title_en": "Console Gaming Station",
        "description_fa": "پلی‌استیشن، دسته و قفسه‌های نورانی برای بازی گروهی. میز کنسول را هماهنگ کنید و با دوستانتان وارد بازی شوید.",
        "description_en": "A PlayStation, controllers, and neon shelves for group play. Arrange a console table and drop into the game with your friends.",
        "external_url": "",
        "internal_url": "/games/",
        "is_active": True,
        "display_order": 2,
    },
    {
        "filename": "Banner3.webp",
        "title_fa": "شکار در شهر تاریک",
        "title_en": "Hunt in the Dark City",
        "description_fa": "نقاب، شنل و کلیسایی در مه. این بنر برای رویدادهای ویژه و سناریوهای تاریک کافه کلاب است.",
        "description_en": "A mask, a cloak, and a cathedral in the fog. This banner introduces Cafe Club’s special events and darker scenarios.",
        "external_url": "",
        "internal_url": "/nights/",
        "is_active": True,
        "display_order": 3,
    },
    {
        "filename": "Banner4.webp",
        "title_fa": "میز کارت و استنتاج",
        "title_en": "The Deduction Table",
        "description_fa": "شمع، کارت و نگاه‌هایی که چیزی را پنهان می‌کنند. دور یک میز بنشینید و ببینید چه کسی حقیقت را می‌گوید.",
        "description_en": "Candles, cards, and glances that hide more than they show. Take a seat and find out who is telling the truth.",
        "external_url": "",
        "internal_url": "/tables/",
        "is_active": True,
        "display_order": 4,
    },
]


def seed_banners(apps, schema_editor):
    Banner = apps.get_model("banners", "Banner")
    seed_dir = Path(__file__).resolve().parent.parent / "seed_images"
    for record in SEED:
        filename = record["filename"]
        destination = f"banners/{filename}"
        if not default_storage.exists(destination):
            default_storage.save(destination, ContentFile((seed_dir / filename).read_bytes()))
        Banner.objects.update_or_create(
            display_order=record["display_order"],
            defaults={
                "title_fa": record["title_fa"],
                "title_en": record["title_en"],
                "description_fa": record["description_fa"],
                "description_en": record["description_en"],
                "external_url": record["external_url"],
                "internal_url": record["internal_url"],
                "is_active": record["is_active"],
                "image": destination,
            },
        )


def unseed_banners(apps, schema_editor):
    Banner = apps.get_model("banners", "Banner")
    Banner.objects.filter(display_order__in=[1, 2, 3, 4]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_banners, unseed_banners),
    ]
