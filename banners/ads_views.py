from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from banners.catalog import package_for_ad_plan
from banners.gateways import gateway_for_source
from banners.geo import ensure_guest_key, navigation_links, parse_coord
from banners.images import optimize_ad_image
from banners.jalali import HOUR_CHOICES, format_jalali_datetime, free_ad_date_choices, parse_event_at
from banners.models import EventAd, EventAdLike
from banners.pay_views import install_source, start_checkout
from banners.promo import CREATE_PLANS, PLANS, PLAN_GOLD, create_plan_key, plan_expires_at, plan_or_none

ADS_PER_MONTH = 3


def _month_start():
    now = timezone.localtime()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _monthly_count(user):
    return EventAd.objects.filter(user=user, created_at__gte=_month_start()).count()


def _ads_unlimited(user):
    return bool(user and (user.is_staff or user.is_superuser))


def purge_expired_ads():
    return 0


def _live_ads():
    purge_expired_ads()
    return (
        EventAd.objects.filter(is_published=True, expires_at__gt=timezone.now())
        .select_related("user__club_profile")
        .annotate(like_count=Count("likes"))
        .order_by("-promo_rank", "-is_boosted", "-boosted_at", "event_at", "expires_at", "id")
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


def _can_boost(request, ad):
    return bool(
        request.user.is_authenticated
        and ad.user_id == request.user.id
        and ad.is_live()
        and ad.promo_plan != PLAN_GOLD
    )


def ads_page(request):
    ads = list(_live_ads())
    liked = _liked_ids(request, ads)
    for ad in ads:
        ad.liked = ad.id in liked
        ad.can_boost = _can_boost(request, ad)
    return render(
        request,
        "banners/ads.html",
        {
            "ads": ads,
            "title": "آگهی",
        },
    )


def ad_detail(request, ad_id):
    purge_expired_ads()
    ad = get_object_or_404(
        EventAd.objects.select_related("user__club_profile").annotate(like_count=Count("likes")),
        pk=ad_id,
        is_published=True,
        expires_at__gt=timezone.now(),
    )
    ad.liked = ad.id in _liked_ids(request, [ad])
    ad.can_boost = _can_boost(request, ad)
    nav_links = []
    if ad.has_nav():
        nav_links = navigation_links(float(ad.latitude), float(ad.longitude), ad.event_name)
    return render(request, "banners/ad_detail.html", {"ad": ad, "nav_links": nav_links})


@require_POST
def like_ad(request, ad_id):
    purge_expired_ads()
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


def _ad_form_context(request, values, remaining, error="", unlimited=False):
    return {
        "needs_blue_tick": False,
        "remaining": max(0, remaining),
        "ads_unlimited": unlimited,
        "values": values,
        "error": error,
        "date_choices": free_ad_date_choices(),
        "hour_choices": HOUR_CHOICES,
        "create_plans": CREATE_PLANS,
        "local_checkout": settings.DEBUG,
        "install_source": install_source(request) if request.user.is_authenticated else "direct",
        "gateway": gateway_for_source(getattr(request, "app_source", "")),
    }


@require_http_methods(["GET", "POST"])
def create_ad(request):
    profile = getattr(request.user, "club_profile", None) if request.user.is_authenticated else None
    if not request.user.is_authenticated or not profile or not profile.is_verified:
        return render(
            request,
            "banners/ad_create.html",
            {
                "needs_blue_tick": True,
                "values": {},
            },
        )

    unlimited = _ads_unlimited(request.user)
    remaining = 99 if unlimited else ADS_PER_MONTH - _monthly_count(request.user)
    values = {
        "event_name": "",
        "organizer_name": "",
        "address": "",
        "event_date": "",
        "event_hour": "",
        "phone": "",
        "ticket_price": "",
        "cafe_bank": "",
        "city": "",
        "district": "",
        "scenario": "",
        "promo_plan": "free",
        "latitude": "",
        "longitude": "",
    }
    error = ""
    if not unlimited and remaining <= 0 and request.method != "POST":
        error = "سقف سه آگهی رایگان در این ماه پر شده است. برای ثبت آگهی جدید یک پلن پولی انتخاب کنید."
    if request.method == "POST":
        values["event_name"] = (request.POST.get("event_name") or "").strip()[:120]
        values["organizer_name"] = (request.POST.get("organizer_name") or "").strip()[:80]
        values["address"] = (request.POST.get("address") or "").strip()[:300]
        values["event_date"] = (request.POST.get("event_date") or "").strip()[:20]
        values["event_hour"] = (request.POST.get("event_hour") or "").strip()[:8]
        values["phone"] = (request.POST.get("phone") or "").strip()[:30]
        values["ticket_price"] = (request.POST.get("ticket_price") or "").strip()[:80]
        values["cafe_bank"] = (request.POST.get("cafe_bank") or "").strip()[:120]
        values["city"] = (request.POST.get("city") or "").strip()[:80]
        values["district"] = (request.POST.get("district") or "").strip()[:120]
        values["scenario"] = (request.POST.get("scenario") or "").strip()[:120]
        values["promo_plan"] = (request.POST.get("promo_plan") or "free").strip()[:12]
        values["latitude"] = (request.POST.get("latitude") or "").strip()
        values["longitude"] = (request.POST.get("longitude") or "").strip()
        plan_key = create_plan_key(values["promo_plan"])
        chosen = PLANS.get(plan_key) if plan_key else None
        upload = request.FILES.get("image")
        required = {
            key: values[key]
            for key in values
            if key not in {"event_date", "event_hour", "promo_plan", "latitude", "longitude"}
        }
        if not unlimited and remaining <= 0 and not plan_key:
            error = "سقف سه آگهی رایگان در این ماه پر شده است."
        elif not all(required.values()) or not upload:
            error = "همه فیلدها و تصویر ایونت را کامل کنید."
        else:
            try:
                event_at = parse_event_at(values["event_date"], values["event_hour"])
                image = optimize_ad_image(upload)
            except ValueError as exc:
                error = str(exc)
            except ValidationError as exc:
                error = " ".join(exc.messages)
            else:
                lat = parse_coord(values["latitude"]) if chosen and chosen["needs_extras"] else None
                lng = parse_coord(values["longitude"]) if chosen and chosen["needs_extras"] else None
                ad = EventAd.objects.create(
                    user=request.user,
                    event_name=values["event_name"],
                    organizer_name=values["organizer_name"],
                    image=image,
                    address=values["address"],
                    starts_at=format_jalali_datetime(event_at),
                    event_at=event_at,
                    phone=values["phone"],
                    ticket_price=values["ticket_price"],
                    cafe_bank=values["cafe_bank"],
                    city=values["city"],
                    district=values["district"],
                    scenario=values["scenario"],
                    expires_at=plan_expires_at(event_at, plan_key),
                    latitude=lat,
                    longitude=lng,
                    is_published=True,
                    is_new=True,
                )
                try:
                    if chosen and chosen["needs_extras"]:
                        update = []
                        for field in ("photo_1", "photo_2", "photo_3"):
                            extra = request.FILES.get(field)
                            if extra:
                                setattr(ad, field, optimize_ad_image(extra))
                                update.append(field)
                        if update:
                            ad.save(update_fields=update)
                except ValidationError as exc:
                    error = " ".join(exc.messages)
                    ad.delete()
                    return render(
                        request,
                        "banners/ad_create.html",
                        _ad_form_context(request, values, remaining, error, unlimited),
                    )
                channel = getattr(request, "app_source", "") or ""
                if plan_key:
                    package = package_for_ad_plan(plan_key)
                    if not package:
                        messages.error(request, "شناسه محصول این پلن در فروشگاه تعریف نشده است.")
                        return redirect("ad_create")
                    ad.boost_requested = True
                    ad.pending_plan = plan_key
                    ad.boost_channel = channel[:12]
                    ad.save(update_fields=["boost_requested", "pending_plan", "boost_channel"])
                    return start_checkout(
                        request,
                        package,
                        event_ad=ad,
                        fail_url=f"/ads/{ad.id}/boost/",
                    )
                messages.success(request, "آگهی شما ثبت شد و تا ۱۲ ساعت پس از زمان برگزاری نمایش داده می‌شود.")
                return redirect("ads")
    return render(request, "banners/ad_create.html", _ad_form_context(request, values, remaining, error, unlimited))


def _live_owner_ad(request, ad_id):
    purge_expired_ads()
    return get_object_or_404(
        EventAd.objects.select_related("user__club_profile"),
        pk=ad_id,
        user=request.user,
        is_published=True,
        expires_at__gt=timezone.now(),
    )


@login_required
@require_http_methods(["GET", "POST"])
def boost_ad(request, ad_id):
    ad = _live_owner_ad(request, ad_id)
    channel = getattr(request, "app_source", "") or ""
    source = install_source(request)
    gateway = gateway_for_source(source)
    if request.method == "POST":
        plan_key = plan_or_none(request.POST.get("plan"))
        if not plan_key:
            messages.error(request, "یکی از پلن‌های برنزی، نقره‌ای یا طلایی را انتخاب کنید.")
            return redirect("ad_boost", ad_id=ad.id)
        chosen = PLANS[plan_key]
        if chosen["rank"] <= (ad.promo_rank or 0):
            messages.info(request, "این آگهی همین پلن یا پلن بالاتر را دارد.")
            return redirect("ads")
        package = package_for_ad_plan(plan_key)
        if not package:
            messages.error(request, "شناسه محصول این پلن در فروشگاه تعریف نشده است.")
            return redirect("ad_boost", ad_id=ad.id)
        ad.boost_requested = True
        ad.pending_plan = plan_key
        ad.boost_channel = channel[:12]
        ad.save(update_fields=["boost_requested", "pending_plan", "boost_channel"])
        return start_checkout(request, package, event_ad=ad, fail_url=f"/ads/{ad.id}/boost/", return_to="ads")
    return render(
        request,
        "banners/ad_boost.html",
        {
            "ad": ad,
            "plans": list(PLANS.values()),
            "gateway": gateway,
            "install_source": source,
            "local_checkout": settings.DEBUG,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def promo_extras(request, ad_id):
    ad = _live_owner_ad(request, ad_id)
    if not ad.allows_extras():
        messages.info(request, "مسیریاب و تصاویر اضافه برای پلن نقره‌ای و طلایی است.")
        return redirect("ad_boost", ad_id=ad.id)
    error = ""
    if request.method == "POST":
        lat = parse_coord(request.POST.get("latitude"))
        lng = parse_coord(request.POST.get("longitude"))
        if lat is None or lng is None:
            error = "محل برگزاری را روی نقشه انتخاب کنید."
        else:
            ad.latitude = lat
            ad.longitude = lng
            update = ["latitude", "longitude"]
            try:
                for field in ("photo_1", "photo_2", "photo_3"):
                    upload = request.FILES.get(field)
                    if upload:
                        setattr(ad, field, optimize_ad_image(upload))
                        update.append(field)
            except ValidationError as exc:
                error = " ".join(exc.messages)
            else:
                ad.save(update_fields=update)
                messages.success(request, "مسیریاب و تصاویر آگهی ذخیره شد.")
                return redirect("ad_detail", ad_id=ad.id)
    return render(
        request,
        "banners/ad_promo_extras.html",
        {
            "ad": ad,
            "error": error,
            "values": {
                "latitude": ad.latitude or "",
                "longitude": ad.longitude or "",
            },
        },
    )
