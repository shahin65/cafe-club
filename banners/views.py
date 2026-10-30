from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _

from banners.app_source import filter_downloads
from banners.models import Banner, LegalPage, SiteLink
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
    banners = Banner.objects.filter(is_active=True)
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
    return render(
        request,
        "banners/home.html",
        {
            "banners": banners,
            "quick_scenarios": quick_scenarios,
            "show_more_scenarios": show_more_scenarios,
            "my_scenarios": mine,
            "my_tournaments": tournaments,
            "can_create_tournament": len(tournaments) < MAX_OPEN,
            "large_scenarios": list(large_scenarios()),
        },
    )


def page(request, page):
    return render(request, "banners/page.html", {"page": PAGES[page]})


def app_settings(request):
    links = SiteLink.objects.filter(is_active=True).exclude(url="")
    downloads = [link for link in links if link.group == SiteLink.GROUP_DOWNLOAD]
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
