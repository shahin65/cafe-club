from banners.models import Venue


def publish_venue_submission(item):
    if not item or not item.pk:
        return None, False
    city = (item.city or "").strip() or "نامشخص"
    existing = Venue.objects.filter(name=item.name, address=item.address, phone=item.phone).first()
    if not item.is_reviewed:
        item.is_reviewed = True
        item.save(update_fields=["is_reviewed"])
    if existing:
        return existing, False
    venue = Venue(
        name=item.name,
        city=city,
        manager_name=item.manager_name,
        address=item.address,
        phone=item.phone,
        hours=item.hours,
        latitude=item.latitude,
        longitude=item.longitude,
        is_active=True,
    )
    if item.logo:
        venue.logo = item.logo
    if item.photo_1:
        venue.photo_1 = item.photo_1
    if item.photo_2:
        venue.photo_2 = item.photo_2
    if item.photo_3:
        venue.photo_3 = item.photo_3
    venue.save()
    return venue, True
