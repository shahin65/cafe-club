from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from banners.images import optimize_ad_image
from banners.models import BlueTickRequest, EventAd

ADS_PER_MONTH = 3
AD_DAYS = 3


def _month_start():
    now = timezone.localtime()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _monthly_count(user):
    return EventAd.objects.filter(user=user, created_at__gte=_month_start()).count()


def _live_ads():
    return EventAd.objects.filter(is_published=True, expires_at__gt=timezone.now())


def ads_page(request):
    return render(
        request,
        "banners/ads.html",
        {"ads": _live_ads(), "title": "آگهی"},
    )


@require_http_methods(["GET", "POST"])
def create_ad(request):
    profile = getattr(request.user, "club_profile", None) if request.user.is_authenticated else None
    pending = None
    if request.user.is_authenticated:
        pending = BlueTickRequest.objects.filter(user=request.user, is_reviewed=False).first()
    if not request.user.is_authenticated or not profile or not profile.is_verified:
        return render(
            request,
            "banners/ad_create.html",
            {
                "needs_blue_tick": True,
                "pending_blue_tick": pending,
                "values": {},
            },
        )

    remaining = ADS_PER_MONTH - _monthly_count(request.user)
    values = {
        "event_name": "",
        "organizer_name": "",
        "address": "",
        "starts_at": "",
        "phone": "",
        "ticket_price": "",
        "cafe_bank": "",
    }
    error = ""
    if remaining <= 0 and request.method != "POST":
        error = "سقف سه آگهی رایگان در این ماه پر شده است."
    if request.method == "POST":
        if remaining <= 0:
            error = "سقف سه آگهی رایگان در این ماه پر شده است."
        else:
            values["event_name"] = (request.POST.get("event_name") or "").strip()[:120]
            values["organizer_name"] = (request.POST.get("organizer_name") or "").strip()[:80]
            values["address"] = (request.POST.get("address") or "").strip()[:300]
            values["starts_at"] = (request.POST.get("starts_at") or "").strip()[:80]
            values["phone"] = (request.POST.get("phone") or "").strip()[:30]
            values["ticket_price"] = (request.POST.get("ticket_price") or "").strip()[:80]
            values["cafe_bank"] = (request.POST.get("cafe_bank") or "").strip()[:120]
            upload = request.FILES.get("image")
            if not all(values.values()) or not upload:
                error = "همه فیلدها و تصویر ایونت را کامل کنید."
            else:
                try:
                    image = optimize_ad_image(upload)
                except ValidationError as exc:
                    error = " ".join(exc.messages)
                else:
                    now = timezone.now()
                    EventAd.objects.create(
                        user=request.user,
                        event_name=values["event_name"],
                        organizer_name=values["organizer_name"],
                        image=image,
                        address=values["address"],
                        starts_at=values["starts_at"],
                        phone=values["phone"],
                        ticket_price=values["ticket_price"],
                        cafe_bank=values["cafe_bank"],
                        expires_at=now + timedelta(days=AD_DAYS),
                        is_published=True,
                        is_new=True,
                    )
                    messages.success(request, "آگهی شما ثبت شد و تا سه روز نمایش داده می‌شود.")
                    return redirect("ads")
    return render(
        request,
        "banners/ad_create.html",
        {
            "needs_blue_tick": False,
            "remaining": max(0, remaining),
            "values": values,
            "error": error,
        },
    )
