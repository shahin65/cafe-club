from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from banners.models import Banner
from scenarios.models import Scenario

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
    "ads": {
        "title": _("آگهی"),
        "body": _("به زودی"),
        "coming_soon": True,
    },
    "location": {
        "title": _("مکان"),
        "body": _("به زودی"),
        "coming_soon": True,
    },
}


def home(request):
    banners = Banner.objects.filter(is_active=True)
    quick_scenarios = Scenario.objects.filter(is_featured=True, owner__isnull=True).prefetch_related("sizes")[:6]
    mine = []
    if request.user.is_authenticated:
        mine = [
            scenario
            for scenario in Scenario.objects.filter(owner=request.user).prefetch_related("sizes__roles", "sizes__final_move_cards")
            if scenario.is_complete()
        ]
    return render(
        request,
        "banners/home.html",
        {"banners": banners, "quick_scenarios": quick_scenarios, "my_scenarios": mine},
    )


def page(request, page):
    return render(request, "banners/page.html", {"page": PAGES[page]})
