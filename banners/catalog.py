from datetime import timedelta

from django.utils import timezone

from banners.models import CoinPackage
from banners.promo import PLANS, VENUE_PLANS, plan_expires_at


def package_for_sku(sku):
    return CoinPackage.objects.filter(sku=sku, is_active=True).first()


def package_for_ad_plan(plan_key):
    plan = PLANS.get(plan_key) or {}
    sku = plan.get("sku")
    return package_for_sku(sku) if sku else None


def package_for_venue_plan(plan_key):
    plan = VENUE_PLANS.get(plan_key) or {}
    sku = plan.get("sku")
    return package_for_sku(sku) if sku else None


def apply_ad_plan(ad, plan_key, channel=""):
    plan = PLANS[plan_key]
    ad.promo_plan = plan_key
    ad.pending_plan = ""
    ad.promo_rank = plan["rank"]
    ad.is_boosted = True
    ad.boosted_at = timezone.now()
    ad.boost_requested = True
    ad.show_on_home = bool(plan["show_on_home"])
    ad.boost_channel = (channel or "")[:12]
    update_fields = [
        "promo_plan",
        "pending_plan",
        "promo_rank",
        "is_boosted",
        "boosted_at",
        "boost_requested",
        "show_on_home",
        "boost_channel",
    ]
    if ad.event_at:
        extra_end = plan_expires_at(ad.event_at, plan_key)
        if extra_end > ad.expires_at:
            ad.expires_at = extra_end
            update_fields.append("expires_at")
    ad.save(update_fields=update_fields)
    return ad


def apply_venue_plan(venue, plan_key, channel=""):
    plan = VENUE_PLANS[plan_key]
    now = timezone.now()
    venue.promo_plan = plan_key
    venue.pending_plan = ""
    venue.promo_rank = plan["rank"]
    venue.show_on_home = bool(plan["show_on_home"])
    venue.boosted_at = now
    venue.boost_requested = True
    venue.boost_channel = (channel or "")[:12]
    venue.promo_expires_at = now + timedelta(days=plan["days"])
    venue.save(
        update_fields=[
            "promo_plan",
            "pending_plan",
            "promo_rank",
            "show_on_home",
            "boosted_at",
            "boost_requested",
            "boost_channel",
            "promo_expires_at",
        ]
    )
    return venue


def fulfill_purchase(txn):
    package = txn.package
    channel = txn.source or txn.gateway
    if package.kind == CoinPackage.KIND_AD and txn.event_ad_id and package.plan_key:
        apply_ad_plan(txn.event_ad, package.plan_key, channel)
    elif package.kind == CoinPackage.KIND_VENUE and txn.venue_id and package.plan_key:
        apply_venue_plan(txn.venue, package.plan_key, channel)
    return txn
