from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image

from banners.jalali import format_jalali_datetime
from banners.models import EventAd, Venue


def _image(color, size, name):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="WEBP", quality=82)
    buffer.seek(0)
    return ContentFile(buffer.read(), name=name)


class Command(BaseCommand):
    help = "Add three sample ads and three sample cafes for visual testing."

    def handle(self, *args, **options):
        user = User.objects.filter(is_superuser=True).order_by("id").first()
        if not user:
            user = User.objects.create_superuser("demo", "demo@example.com", "demo-pass-123")
        profile = user.club_profile
        if not profile.is_verified:
            profile.is_verified = True
            profile.display_name = profile.display_name or "میزبان نمایشی"
            profile.save(update_fields=["is_verified", "display_name"])
        venues = self._venues()
        ads = self._ads(user)
        self.stdout.write(self.style.SUCCESS(f"{venues} کافه و {ads} آگهی نمایشی آماده شد."))

    def _venues(self):
        created = 0
        samples = [
            {
                "name": "کافه نمایشی شب",
                "city": "تهران",
                "manager_name": "سارا میزبان",
                "address": "ولیعصر، بالاتر از پارک‌وی",
                "phone": "02122001122",
                "hours": "شنبه تا پنجشنبه ۱۸ تا ۲",
                "latitude": "35.772100",
                "longitude": "51.418600",
                "logo": (40, 20, 70),
                "photos": [(90, 40, 50), (50, 30, 80), (30, 50, 70)],
            },
            {
                "name": "کلاب نمایشی باران",
                "city": "کرج",
                "manager_name": "نیما گرداننده",
                "address": "جهانشهر، بلوار مولوی",
                "phone": "02632223344",
                "hours": "چهارشنبه تا جمعه ۲۰ تا ۳",
                "latitude": "35.832700",
                "longitude": "50.991500",
                "logo": (20, 70, 80),
                "photos": [(20, 50, 60), (40, 80, 70), (10, 40, 55)],
            },
            {
                "name": "کافه نمایشی ونک",
                "city": "تهران",
                "manager_name": "مریم سوپروایزر",
                "address": "ونک، خیابان گاندی",
                "phone": "02188887766",
                "hours": "هر شب ۱۹ تا ۲۴",
                "latitude": "35.757200",
                "longitude": "51.414400",
                "logo": (120, 70, 30),
                "photos": [(140, 80, 40), (90, 50, 20), (70, 40, 30)],
            },
        ]
        for item in samples:
            venue, was_created = Venue.objects.get_or_create(
                name=item["name"],
                defaults={
                    "city": item["city"],
                    "manager_name": item["manager_name"],
                    "address": item["address"],
                    "phone": item["phone"],
                    "hours": item["hours"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "is_active": True,
                },
            )
            if not was_created:
                continue
            venue.logo.save(f"{venue.id}-logo.webp", _image(item["logo"], (512, 512), "logo.webp"), save=False)
            for index, color in enumerate(item["photos"], start=1):
                getattr(venue, f"photo_{index}").save(
                    f"{venue.id}-photo-{index}.webp",
                    _image(color, (1200, 800), f"photo-{index}.webp"),
                    save=False,
                )
            venue.save()
            created += 1
        return created

    def _ads(self, user):
        created = 0
        now = timezone.localtime()
        samples = [
            {
                "event_name": "ایونت نمایشی مافیا",
                "organizer_name": "علی میزبان",
                "address": "کافه نمایشی شب، ولیعصر",
                "phone": "09121112233",
                "ticket_price": "۲۵۰ هزار تومان",
                "cafe_bank": "کافه نمایشی شب",
                "city": "تهران",
                "district": "پارک‌وی",
                "scenario": "بازپرس",
                "hours": 26,
                "color": (90, 30, 40),
            },
            {
                "event_name": "ایونت نمایشی پانتومیم",
                "organizer_name": "سارا اجرا",
                "address": "کلاب نمایشی باران، جهانشهر",
                "phone": "09123334455",
                "ticket_price": "۱۸۰ هزار تومان",
                "cafe_bank": "کلاب نمایشی باران",
                "city": "کرج",
                "district": "جهانشهر",
                "scenario": "پانتومیم",
                "hours": 30,
                "color": (30, 70, 90),
            },
            {
                "event_name": "ایونت نمایشی گل یا پوچ",
                "organizer_name": "نیما تورنمنت",
                "address": "کافه نمایشی ونک، گاندی",
                "phone": "09125556677",
                "ticket_price": "رایگان",
                "cafe_bank": "کافه نمایشی ونک",
                "city": "تهران",
                "district": "ونک",
                "scenario": "گل یا پوچ",
                "hours": 34,
                "color": (120, 80, 30),
            },
        ]
        for item in samples:
            if EventAd.objects.filter(event_name=item["event_name"]).exists():
                continue
            event_at = now + timedelta(hours=item["hours"])
            ad = EventAd(
                user=user,
                event_name=item["event_name"],
                organizer_name=item["organizer_name"],
                address=item["address"],
                starts_at=format_jalali_datetime(event_at),
                event_at=event_at,
                phone=item["phone"],
                ticket_price=item["ticket_price"],
                cafe_bank=item["cafe_bank"],
                city=item["city"],
                district=item["district"],
                scenario=item["scenario"],
                expires_at=event_at + timedelta(hours=12),
                is_published=True,
                is_new=True,
            )
            ad.image.save(
                f"demo-{item['hours']}.webp",
                _image(item["color"], (1280, 720), "ad.webp"),
                save=False,
            )
            ad.save()
            created += 1
        return created
