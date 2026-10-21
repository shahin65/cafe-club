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
}


def home(request):
    banners = Banner.objects.filter(is_active=True)
    quick_scenarios = Scenario.objects.filter(is_featured=True).prefetch_related("sizes")[:6]
    return render(
        request,
        "banners/home.html",
        {"banners": banners, "quick_scenarios": quick_scenarios},
    )


def page(request, page):
    return render(request, "banners/page.html", {"page": PAGES[page]})
