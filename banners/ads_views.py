from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from banners.geo import IRAN_CITIES, ensure_guest_key
from banners.images import optimize_ad_image
from banners.models import BlueTickRequest, EventAd, EventAdLike

ADS_PER_MONTH = 3
AD_DAYS = 3


def _month_start():
    now = timezone.localtime()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _monthly_count(user):
    return EventAd.objects.filter(user=user, created_at__gte=_month_start()).count()


def _live_ads():
    return (
        EventAd.objects.filter(is_published=True, expires_at__gt=timezone.now())
        .select_related("user__club_profile")
        .annotate(like_count=Count("likes"))
    )


def _liked_ids(request, ads):
    ids = [ad.id for ad in ads]
    if not ids:
        return set()
    if request.user.is_authenticated:
        return set(EventAdLike.objects.filter(ad_id__in=ids, user=request.user).values_list("ad_id", flat=True))
    guest_key = request.session.get("places_guest_key") or ""
    if not guest_key:
        return set()
    return set(
        EventAdLike.objects.filter(ad_id__in=ids, user__isnull=True, guest_key=guest_key).values_list("ad_id", flat=True)
    )


def ads_page(request):
    ads = list(_live_ads())
    liked = _liked_ids(request, ads)
    for ad in ads:
        ad.liked = ad.id in liked
    return render(request, "banners/ads.html", {"ads": ads, "title": "آگهی"})


def ad_detail(request, ad_id):
    ad = get_object_or_404(
        EventAd.objects.select_related("user__club_profile").annotate(like_count=Count("likes")),
        pk=ad_id,
        is_published=True,
        expires_at__gt=timezone.now(),
    )
    ad.liked = ad.id in _liked_ids(request, [ad])
    return render(request, "banners/ad_detail.html", {"ad": ad})


@require_POST
def like_ad(request, ad_id):
    ad = get_object_or_404(EventAd, pk=ad_id, is_published=True, expires_at__gt=timezone.now())
    if request.user.is_authenticated:
        like = EventAdLike.objects.filter(ad=ad, user=request.user).first()
        if like:
            like.delete()
        else:
            EventAdLike.objects.create(ad=ad, user=request.user, guest_key="")
    else:
        guest_key = ensure_guest_key(request)
        like = EventAdLike.objects.filter(ad=ad, user__isnull=True, guest_key=guest_key).first()
        if like:
            like.delete()
        else:
            EventAdLike.objects.create(ad=ad, user=None, guest_key=guest_key)
    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("ad_detail", ad_id=ad.id)


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
                "cities": IRAN_CITIES,
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
        "city": "",
        "district": "",
        "scenario": "",
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
            values["city"] = (request.POST.get("city") or "").strip()[:80]
            values["district"] = (request.POST.get("district") or "").strip()[:120]
            values["scenario"] = (request.POST.get("scenario") or "").strip()[:120]
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
                        city=values["city"],
                        district=values["district"],
                        scenario=values["scenario"],
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
            "cities": IRAN_CITIES,
        },
    )
