from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from banners.geo import (
    CITY_SESSION_KEY,
    captcha_is_valid,
    captcha_prompt,
    consume_captcha,
    ensure_guest_key,
    format_distance,
    haversine_km,
    issue_sum_captcha,
    navigation_links,
    parse_coord,
)
from banners.accounts import COMMENT_RECEIVED, comment_author_name
from banners.catalog import package_for_venue_plan
from banners.gateways import gateway_for_source
from banners.images import optimize_venue_image
from banners.models import Venue, VenueComment, VenueRating, VenueSubmission
from banners.pay_views import install_source, start_checkout
from banners.promo import VENUE_PLANS, venue_plan_or_none
from scenarios.staff import can_manage_listings

SORTS = ("name", "distance", "rating")
PAGE_SIZE = 10


def _active_venues():
    return Venue.objects.filter(is_active=True).annotate(
        avg_rating=Avg("ratings__stars"),
        rating_count=Count("ratings", distinct=True),
        comment_count=Count("comments", filter=Q(comments__is_approved=True), distinct=True),
    )


def _user_point(request):
    lat = parse_coord(request.GET.get("lat") or request.POST.get("lat"))
    lng = parse_coord(request.GET.get("lng") or request.POST.get("lng"))
    if lat is None or lng is None:
        return None, None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None, None
    return lat, lng


def _decorate(venues, lat, lng):
    items = []
    for venue in venues:
        point = venue.maps_point()
        distance = haversine_km(lat, lng, point[0], point[1]) if point and lat is not None else None
        venue.distance_km = distance
        venue.distance_label = format_distance(distance)
        venue.avg_display = round(venue.avg_rating, 1) if venue.avg_rating else None
        items.append(venue)
    return items


def _promo_key(venue):
    live = venue.is_promo_live()
    boosted = venue.boosted_at.timestamp() if live and venue.boosted_at else 0
    return (0 if live else 1, -(venue.promo_rank or 0) if live else 0, -boosted)


def _sort_venues(venues, sort, has_point):
    if sort == "name":
        items = sorted(venues, key=lambda item: item.name)
    elif sort == "distance" and has_point:
        items = sorted(venues, key=lambda item: (item.distance_km is None, item.distance_km or 0, item.name))
    else:
        items = sorted(
            venues,
            key=lambda item: (
                -(item.avg_rating or 0),
                -(item.rating_count or 0),
                item.name,
            ),
        )
    return sorted(items, key=_promo_key)


def _nav_for(venue):
    point = venue.maps_point()
    if not point:
        return []
    return navigation_links(point[0], point[1], venue.name)


def _nearest(venues):
    with_distance = [venue for venue in venues if venue.distance_km is not None]
    if not with_distance:
        with_point = [venue for venue in venues if venue.has_point()]
        return with_point[0] if with_point else None
    return min(with_distance, key=lambda item: item.distance_km)


def _page_size(request):
    try:
        shown = int(request.GET.get("shown") or PAGE_SIZE)
    except (TypeError, ValueError):
        shown = PAGE_SIZE
    return max(PAGE_SIZE, min(shown, 200))


def _filter_query(lat, lng, city, query, sort, shown=None):
    data = {}
    if lat is not None:
        data["lat"] = f"{lat:.6f}"
    if lng is not None:
        data["lng"] = f"{lng:.6f}"
    if city:
        data["city"] = city
    if query:
        data["q"] = query
    if sort:
        data["sort"] = sort
    if shown:
        data["shown"] = str(shown)
    return urlencode(data)


@require_http_methods(["GET", "POST"])
def places(request):
    if request.method == "POST" and request.POST.get("set_city") is not None:
        city = (request.POST.get("city") or "").strip()[:80]
        if city:
            request.session[CITY_SESSION_KEY] = city
        else:
            request.session.pop(CITY_SESSION_KEY, None)
        request.session.modified = True
        return redirect("location")

    if "city" in request.GET:
        selected_city = (request.GET.get("city") or "").strip()[:80]
        if selected_city:
            request.session[CITY_SESSION_KEY] = selected_city
        else:
            request.session.pop(CITY_SESSION_KEY, None)
        request.session.modified = True
    else:
        selected_city = (request.session.get(CITY_SESSION_KEY) or "").strip()

    query = (request.GET.get("q") or "").strip()[:80]
    sort = request.GET.get("sort") if request.GET.get("sort") in SORTS else "distance"
    lat, lng = _user_point(request)
    queryset = _active_venues()
    cities = list(queryset.order_by("city").values_list("city", flat=True).distinct())
    if selected_city:
        queryset = queryset.filter(city=selected_city)
    if query:
        lookup = Q(name__icontains=query) | Q(address__icontains=query) | Q(manager_name__icontains=query)
        digits = query.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        if digits.isdigit():
            lookup |= Q(public_id=int(digits))
        queryset = queryset.filter(lookup)
    venues = _decorate(list(queryset), lat, lng)
    if sort == "distance" and lat is None:
        sort = "rating"
    venues = _sort_venues(venues, sort, lat is not None)
    shown = _page_size(request)
    has_more = len(venues) > shown
    next_shown = min(len(venues), shown + PAGE_SIZE)
    visible = venues[:shown]
    nearest = _nearest(venues)
    return render(
        request,
        "banners/places.html",
        {
            "venues": visible,
            "cities": cities,
            "selected_city": selected_city,
            "query": query,
            "sort": sort,
            "user_lat": lat,
            "user_lng": lng,
            "nearest": nearest,
            "nearest_nav": _nav_for(nearest) if nearest else [],
            "has_more": has_more,
            "more_query": _filter_query(lat, lng, selected_city, query, sort, next_shown),
            "filter_query": _filter_query(lat, lng, selected_city, query, sort),
        },
    )


@require_GET
def venue_detail(request, venue_id):
    venue = get_object_or_404(_active_venues(), pk=venue_id)
    lat, lng = _user_point(request)
    _decorate([venue], lat, lng)
    left, right = captcha_prompt(request)
    comments = venue.comments.filter(is_approved=True).order_by("-created_at")
    my_stars = None
    if request.user.is_authenticated:
        mine = venue.ratings.filter(user=request.user).first()
    else:
        mine = venue.ratings.filter(user__isnull=True, guest_key=request.session.get("places_guest_key") or "").first()
    if mine:
        my_stars = mine.stars
    return render(
        request,
        "banners/venue.html",
        {
            "venue": venue,
            "comments": comments,
            "captcha_left": left,
            "captcha_right": right,
            "my_stars": my_stars,
            "nav_links": _nav_for(venue),
            "user_lat": lat,
            "user_lng": lng,
        },
    )


@require_POST
def rate_venue(request, venue_id):
    venue = get_object_or_404(Venue, pk=venue_id, is_active=True)
    try:
        stars = int(request.POST.get("stars") or 0)
    except (TypeError, ValueError):
        stars = 0
    if stars not in {1, 2, 3, 4, 5}:
        messages.error(request, "امتیاز باید بین ۱ تا ۵ ستاره باشد.")
        return redirect("venue_detail", venue_id=venue.id)
    if request.user.is_authenticated:
        rating, _created = VenueRating.objects.get_or_create(
            venue=venue,
            user=request.user,
            defaults={"stars": stars, "guest_key": ""},
        )
        if rating.stars != stars:
            rating.stars = stars
            rating.save(update_fields=["stars", "updated_at"])
    else:
        guest_key = ensure_guest_key(request)
        rating, _created = VenueRating.objects.get_or_create(
            venue=venue,
            user=None,
            guest_key=guest_key,
            defaults={"stars": stars},
        )
        if rating.stars != stars:
            rating.stars = stars
            rating.save(update_fields=["stars", "updated_at"])
    messages.success(request, "امتیاز شما ثبت شد.")
    return redirect("venue_detail", venue_id=venue.id)


@require_POST
def comment_venue(request, venue_id):
    venue = get_object_or_404(Venue, pk=venue_id, is_active=True)
    if (request.POST.get("website") or "").strip():
        raise Http404
    name = comment_author_name(request)
    body = (request.POST.get("body") or "").strip()[:1000]
    answer = request.POST.get("captcha") or ""
    if not name or not body:
        messages.error(
            request,
            "متن نظر را وارد کنید." if request.user.is_authenticated else "نام و متن نظر را وارد کنید.",
        )
        issue_sum_captcha(request)
        return redirect("venue_detail", venue_id=venue.id)
    if not captcha_is_valid(request, answer):
        messages.error(request, "جمع دو عدد را درست وارد کنید.")
        issue_sum_captcha(request)
        return redirect("venue_detail", venue_id=venue.id)
    VenueComment.objects.create(venue=venue, author_name=name, body=body, is_approved=False)
    consume_captcha(request)
    messages.success(request, COMMENT_RECEIVED)
    return redirect("venue_detail", venue_id=venue.id)


INTRO_TEXT = (
    "اگر شما مالک یک کافه یا کلاب مافیا هستید و در هفته بیش از دو روز ثابت بازی مافیا ران می‌کنید "
    "فرم اطلاعات ذیل را تکمیل و برای ما ارسال کنید تا کلاب شما در لیست به ثبت برسد"
)
THANKS_TEXT = "مورد ارسالی طی 72 ساعت آینده بررسی و به شما اطلاع‌رسانی خواهد شد"


def _empty_venue_values():
    return {
        "name": "",
        "manager_name": "",
        "address": "",
        "phone": "",
        "hours": "",
        "latitude": "",
        "longitude": "",
        "city": "",
    }


def _venue_values_from_post(request):
    values = _empty_venue_values()
    values["name"] = (request.POST.get("name") or "").strip()[:120]
    values["manager_name"] = (request.POST.get("manager_name") or "").strip()[:80]
    values["address"] = (request.POST.get("address") or "").strip()[:300]
    values["phone"] = (request.POST.get("phone") or "").strip()[:30]
    values["hours"] = (request.POST.get("hours") or "").strip()[:200]
    values["city"] = (request.POST.get("city") or "").strip()[:80]
    values["latitude"] = (request.POST.get("latitude") or "").strip()
    values["longitude"] = (request.POST.get("longitude") or "").strip()
    return values


def _venue_values_from_obj(venue):
    return {
        "name": venue.name,
        "manager_name": venue.manager_name,
        "address": venue.address,
        "phone": venue.phone,
        "hours": venue.hours,
        "city": venue.city,
        "latitude": venue.latitude or "",
        "longitude": venue.longitude or "",
    }


def _apply_venue_files(venue, request, *, logo_required):
    logo = request.FILES.get("logo")
    if logo:
        venue.logo = _save_upload(logo, 512)
    elif logo_required:
        raise ValidationError("لوگوی کلاب را انتخاب کنید.")
    extras = [request.FILES.get("photo_1"), request.FILES.get("photo_2"), request.FILES.get("photo_3")]
    extras = [item for item in extras if item]
    if len(extras) > 3:
        raise ValidationError("حداکثر سه تصویر می‌توانید ارسال کنید.")
    photos = [_save_upload(item, 1200) for item in extras]
    if len(photos) > 0:
        venue.photo_1 = photos[0]
    if len(photos) > 1:
        venue.photo_2 = photos[1]
    if len(photos) > 2:
        venue.photo_3 = photos[2]


def _fill_venue_fields(venue, values, lat, lng):
    venue.name = values["name"]
    venue.manager_name = values["manager_name"]
    venue.address = values["address"]
    venue.phone = values["phone"]
    venue.hours = values["hours"]
    venue.city = values["city"]
    venue.latitude = lat
    venue.longitude = lng


def _save_upload(upload, max_edge):
    if not upload:
        return None
    return optimize_venue_image(upload, max_edge=max_edge)


@require_http_methods(["GET", "POST"])
def submit_venue(request):
    staff_direct = can_manage_listings(request.user)
    values = _empty_venue_values()
    error = ""
    if request.method == "POST":
        values = _venue_values_from_post(request)
        lat = parse_coord(values["latitude"])
        lng = parse_coord(values["longitude"])
        required = {key: values[key] for key in ("name", "manager_name", "address", "phone", "hours", "city")}
        if not all(required.values()):
            error = "نام کلاب، نام مدیر، شهر، آدرس، تلفن و ساعات کاری را کامل کنید."
        elif lat is None or lng is None:
            error = "محل کافه یا کلاب را روی نقشه انتخاب کنید."
        elif staff_direct:
            try:
                venue = Venue(is_active=True)
                _fill_venue_fields(venue, values, lat, lng)
                _apply_venue_files(venue, request, logo_required=True)
                venue.save()
            except ValidationError as exc:
                error = " ".join(exc.messages)
            else:
                messages.success(request, "کافه یا کلاب در سایت منتشر شد.")
                return redirect("venue_detail", venue_id=venue.id)
        else:
            logo = request.FILES.get("logo")
            extras = [item for item in (request.FILES.get("photo_1"), request.FILES.get("photo_2"), request.FILES.get("photo_3")) if item]
            if not logo:
                error = "نام کلاب، لوگو، نام مدیر، شهر، آدرس، تلفن و ساعات کاری را کامل کنید."
            elif len(extras) > 3:
                error = "حداکثر سه تصویر می‌توانید ارسال کنید."
            else:
                try:
                    submission = VenueSubmission(
                        user=request.user if request.user.is_authenticated else None,
                        name=values["name"],
                        manager_name=values["manager_name"],
                        address=values["address"],
                        phone=values["phone"],
                        hours=values["hours"],
                        city=values["city"],
                        latitude=lat,
                        longitude=lng,
                        logo=_save_upload(logo, 512),
                    )
                    photos = [_save_upload(item, 1200) for item in extras]
                    if len(photos) > 0:
                        submission.photo_1 = photos[0]
                    if len(photos) > 1:
                        submission.photo_2 = photos[1]
                    if len(photos) > 2:
                        submission.photo_3 = photos[2]
                    submission.save()
                except ValidationError as exc:
                    error = " ".join(exc.messages)
                else:
                    return render(
                        request,
                        "banners/venue_submit.html",
                        {
                            "submitted": True,
                            "thanks": THANKS_TEXT,
                            "intro": INTRO_TEXT,
                            "values": values,
                            "staff_direct": False,
                        },
                    )
    return render(
        request,
        "banners/venue_submit.html",
        {
            "submitted": False,
            "intro": "کافه یا کلاب را همین‌جا ثبت کنید تا بلافاصله در صفحه کجا برم؟ نمایش داده شود."
            if staff_direct
            else INTRO_TEXT,
            "error": error,
            "values": values,
            "staff_direct": staff_direct,
        },
    )


@login_required(login_url="profile")
@require_http_methods(["GET", "POST"])
def edit_venue(request, venue_id):
    if not can_manage_listings(request.user):
        messages.error(request, "اجازه این کار را ندارید.")
        return redirect("location")
    venue = get_object_or_404(Venue, pk=venue_id)
    values = _venue_values_from_obj(venue)
    error = ""
    if request.method == "POST":
        values = _venue_values_from_post(request)
        lat = parse_coord(values["latitude"])
        lng = parse_coord(values["longitude"])
        required = {key: values[key] for key in ("name", "manager_name", "address", "phone", "hours", "city")}
        if not all(required.values()):
            error = "نام کلاب، نام مدیر، شهر، آدرس، تلفن و ساعات کاری را کامل کنید."
        elif lat is None or lng is None:
            error = "محل کافه یا کلاب را روی نقشه انتخاب کنید."
        else:
            try:
                _fill_venue_fields(venue, values, lat, lng)
                _apply_venue_files(venue, request, logo_required=False)
                venue.save()
            except ValidationError as exc:
                error = " ".join(exc.messages)
            else:
                messages.success(request, "اطلاعات کافه یا کلاب ذخیره شد.")
                return redirect("venue_detail", venue_id=venue.id)
    return render(
        request,
        "banners/venue_submit.html",
        {
            "submitted": False,
            "intro": "اطلاعات کافه یا کلاب را ویرایش کنید.",
            "error": error,
            "values": values,
            "staff_direct": True,
            "venue": venue,
        },
    )


def _public_id_from_text(raw):
    translated = (raw or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    digits = "".join(ch for ch in translated if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def _new_venue_from_promo(request, values):
    lat = parse_coord(values["latitude"])
    lng = parse_coord(values["longitude"])
    logo = request.FILES.get("logo")
    extras = [item for item in (request.FILES.get("photo_1"), request.FILES.get("photo_2"), request.FILES.get("photo_3")) if item]
    required = {key: values[key] for key in ("name", "manager_name", "address", "phone", "hours", "city")}
    if not all(required.values()) or not logo:
        raise ValidationError("برای ثبت کافه، نام، لوگو، نام مدیر، شهر، آدرس، تلفن و ساعات کاری را کامل کنید.")
    if lat is None or lng is None:
        raise ValidationError("محل کافه یا کلاب را روی نقشه انتخاب کنید.")
    if len(extras) > 3:
        raise ValidationError("حداکثر سه تصویر می‌توانید ارسال کنید.")
    venue = Venue(
        name=values["name"],
        manager_name=values["manager_name"],
        address=values["address"],
        phone=values["phone"],
        hours=values["hours"],
        city=values["city"],
        latitude=lat,
        longitude=lng,
        logo=_save_upload(logo, 512),
        is_active=True,
    )
    photos = [_save_upload(item, 1200) for item in extras]
    if len(photos) > 0:
        venue.photo_1 = photos[0]
    if len(photos) > 1:
        venue.photo_2 = photos[1]
    if len(photos) > 2:
        venue.photo_3 = photos[2]
    venue.save()
    return venue


@login_required
@require_http_methods(["GET", "POST"])
def venue_promo(request):
    values = {
        "promo_plan": "bronze",
        "venue_mode": "existing",
        "venue_id": "",
        "name": "",
        "manager_name": "",
        "address": "",
        "phone": "",
        "hours": "",
        "latitude": "",
        "longitude": "",
        "city": "",
    }
    error = ""
    if request.method == "POST":
        for key in values:
            if key in request.POST:
                values[key] = (request.POST.get(key) or "").strip()
        plan_key = venue_plan_or_none(values["promo_plan"])
        chosen = VENUE_PLANS.get(plan_key) if plan_key else None
        if not chosen:
            error = "یکی از پلن‌های برنزی، نقره‌ای یا طلایی را انتخاب کنید."
        else:
            try:
                if values["venue_mode"] == "new":
                    venue = _new_venue_from_promo(request, values)
                else:
                    public_id = _public_id_from_text(values["venue_id"])
                    venue = Venue.objects.filter(public_id=public_id, is_active=True).first() if public_id else None
                    if not venue:
                        raise ValidationError("شناسه کافه پیدا نشد. اگر کافه ثبت نشده، حالت ثبت کافه جدید را انتخاب کنید.")
                channel = getattr(request, "app_source", "") or ""
                package = package_for_venue_plan(plan_key)
                if not package:
                    raise ValidationError("شناسه محصول این پلن در فروشگاه تعریف نشده است.")
                venue.boost_requested = True
                venue.pending_plan = plan_key
                venue.boost_channel = channel[:12]
                venue.save(update_fields=["boost_requested", "pending_plan", "boost_channel"])
                return start_checkout(request, package, venue=venue, fail_url="venue_promo")
            except ValidationError as exc:
                error = " ".join(exc.messages)
    return render(
        request,
        "banners/venue_promo.html",
        {
            "values": values,
            "error": error,
            "plans": list(VENUE_PLANS.values()),
            "local_checkout": settings.DEBUG,
            "install_source": install_source(request),
            "gateway": gateway_for_source(getattr(request, "app_source", "")),
        },
    )
