from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from banners.models import UserProfile, allocate_public_id


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, public_id=allocate_public_id())
        return
    profile, _made = UserProfile.objects.get_or_create(user=instance, defaults={"public_id": allocate_public_id()})
    if (instance.is_staff or instance.is_superuser) and not profile.is_gold_verified:
        profile.is_gold_verified = True
        profile.save(update_fields=["is_gold_verified"])
