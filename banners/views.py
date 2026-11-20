from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from banners.app_source import filter_downloads
from banners.models import Banner, EventAd, LegalPage, SiteLink, SiteSettings, Venue
from banners.tournament import MAX_OPEN, owned_tournaments
from scenarios.large_deal import large_scenarios
from scenarios.models import GUEST_SCENARIO_KEY, Scenario
from scenarios.pins import home_quick_scenarios

PAGES = {
    "nights": {
        "title": _("شب‌های بازی"),
        "body": _(
            "شب‌های نقش‌آفرینی و سناریوهای شهری کافه کلاب اینجاست. "
            "برنامه رویدادها از پنل مدیریت به‌روز می‌شود."
        ),
    },
    "games": {
        "title": _("بازی‌ها"),
        "body": _(
            "میزهای کنسول برای بازی گروهی آماده‌اند. "
            "زمان میز را هماهنگ کنید و با دوستان‌تان بازی را شروع کنید."
        ),
    },
    "tables": {
        "title": _("میزها"),
        "body": _(
            "کارت، استنتاج و گفت‌وگوی روبه‌رو. "
            "یک میز انتخاب کنید و ببینید چه کسی حقیقت را می‌گوید."
        ),
    },
}


def home(request):
    if SiteSettings.load().show_home_banners:
        banners = Banner.objects.filter(is_active=True)
    else:
        banners = Banner.objects.none()
    quick_scenarios, show_more_scenarios = home_quick_scenarios(request)
    if request.user.is_authenticated:
        owned = Scenario.objects.filter(owner=request.user)
    else:
        guest_key = request.session.get(GUEST_SCENARIO_KEY) or ""
        owned = Scenario.objects.filter(owner__isnull=True, guest_key=guest_key) if guest_key else Scenario.objects.none()
    mine = [
        scenario
        for scenario in owned.prefetch_related("sizes__roles", "sizes__final_move_cards")
        if scenario.is_complete()
    ]
    tournaments = list(owned_tournaments(request)[:MAX_OPEN])
    featured_ads = _featured_home_items()
    return render(
        request,
        "banners/home.html",
        {
            "banners": banners,
            "featured_ads": featured_ads,
            "quick_scenarios": quick_scenarios,
            "show_more_scenarios": show_more_scenarios,
            "my_scenarios": mine,
            "my_tournaments": tournaments,
            "can_create_tournament": len(tournaments) < MAX_OPEN,
            "large_scenarios": list(large_scenarios()),
        },
    )


def _featured_home_items():
    now = timezone.now()
    items = []
    for ad in EventAd.objects.filter(
        is_published=True,
        show_on_home=True,
        expires_at__gt=now,
    ).order_by("-boosted_at", "-id"):
        items.append(
            {
                "key": f"ad-{ad.id}",
                "href": reverse("ad_detail", args=[ad.id]),
                "image_url": ad.image.url,
                "title": ad.event_name,
                "subtitle": ad.scenario or "",
                "meta": " · ".join(part for part in (ad.city, ad.district) if part),
                "sort": ad.boosted_at or ad.created_at,
            }
        )
    for venue in Venue.objects.filter(
        is_active=True,
        show_on_home=True,
        promo_expires_at__gt=now,
    ).order_by("-boosted_at", "-id"):
        cover = venue.cover_image()
        items.append(
            {
                "key": f"venue-{venue.id}",
                "href": reverse("venue_detail", args=[venue.id]),
                "image_url": cover.url if cover else "",
                "title": venue.name,
                "subtitle": "",
                "meta": " · ".join(part for part in (venue.city, venue.address) if part),
                "sort": venue.boosted_at or venue.created_at,
            }
        )
    items.sort(key=lambda item: item["sort"] or now, reverse=True)
    return items[:8]


def page(request, page):
    return render(request, "banners/page.html", {"page": PAGES[page]})


def app_settings(request):
    links = SiteLink.objects.filter(is_active=True).exclude(url="")
    downloads = [link for link in links if link.group == SiteLink.GROUP_DOWNLOAD and link.key != SiteLink.KEY_ANDROID]
    downloads = filter_downloads(downloads, getattr(request, "app_source", ""))
    socials = [link for link in links if link.group == SiteLink.GROUP_SOCIAL]
    return render(
        request,
        "banners/settings.html",
        {"downloads": downloads, "socials": socials},
    )


def legal_page(request, key):
    page = get_object_or_404(LegalPage, key=key)
    return render(request, "banners/legal.html", {"legal": page})
