from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from banners.models import Banner, SiteLink
from scenarios.models import GUEST_SCENARIO_KEY, Scenario

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
    quick_scenarios = Scenario.objects.filter(is_featured=True, owner__isnull=True, guest_key="").prefetch_related("sizes")[:6]
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
    return render(
        request,
        "banners/home.html",
        {"banners": banners, "quick_scenarios": quick_scenarios, "my_scenarios": mine},
    )


def page(request, page):
    return render(request, "banners/page.html", {"page": PAGES[page]})


def app_settings(request):
    links = SiteLink.objects.filter(is_active=True).exclude(url="")
    downloads = [link for link in links if link.group == SiteLink.GROUP_DOWNLOAD]
    socials = [link for link in links if link.group == SiteLink.GROUP_SOCIAL]
    return render(
        request,
        "banners/settings.html",
        {"downloads": downloads, "socials": socials},
    )
