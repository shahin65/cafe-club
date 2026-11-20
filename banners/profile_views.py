from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from banners.images import optimize_profile_photo
from banners.models import (
    GOLD_TICK_REJECTED_MESSAGE,
    GOLD_TICK_WAIT_MESSAGE,
    BlueTickRequest,
)
from banners.telegram import telegram_public_context


def _safe_next(request, fallback="profile"):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url.startswith("/") and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return reverse(fallback)


def gold_tick_state(user):
    pending = None
    rejected = None
    if getattr(user, "is_authenticated", False):
        pending = BlueTickRequest.objects.filter(user=user, is_reviewed=False).first()
        latest = BlueTickRequest.objects.filter(user=user).order_by("-created_at").first()
        if (
            not pending
            and latest
            and latest.status == BlueTickRequest.STATUS_REJECTED
        ):
            rejected = latest
    return {"pending_gold_tick": pending, "rejected_gold_tick": rejected}


def blue_tick_state(user):
    return gold_tick_state(user)


def profile_page_context(request, extra=None):
    profile = request.user.club_profile if request.user.is_authenticated else None
    my_ads = []
    if request.user.is_authenticated:
        my_ads = list(request.user.event_ads.all().order_by("-created_at", "-id"))
    pending_paid = (request.session.get("pending_paid_display_name") or "").strip()
    context = {
        "club_profile": profile,
        "my_ads": my_ads,
        "show_auth_methods": bool(pending_paid and not request.user.is_authenticated),
        "telegram": telegram_public_context(),
        "telegram_linked": bool(profile and profile.telegram_chat_id),
        "bale_linked": bool(profile and profile.bale_chat_id),
        "gold_tick_wait_message": GOLD_TICK_WAIT_MESSAGE,
        "gold_tick_rejected_message": GOLD_TICK_REJECTED_MESSAGE,
    }
    context.update(gold_tick_state(request.user))
    if extra:
        context.update(extra)
    return context


def profile_page(request):
    return render(request, "account/profile.html", profile_page_context(request))


@require_http_methods(["POST"])
def save_profile_details(request):
    if not request.user.is_authenticated:
        return redirect("login")
    profile = request.user.club_profile
    if not profile.is_verified:
        messages.error(request, "فقط کاربران دارای تیک آبی می‌توانند عکس و بیوگرافی بگذارند.")
        return redirect("profile")
    bio = (request.POST.get("bio") or "").strip()[:280]
    profile.bio = bio
    upload = request.FILES.get("photo")
    if upload:
        try:
            profile.photo = optimize_profile_photo(upload)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("profile")
    profile.save()
    messages.success(request, "پروفایل ذخیره شد.")
    return redirect("profile")


@require_POST
def request_gold_tick(request):
    if not request.user.is_authenticated:
        messages.error(request, "برای درخواست تیک طلایی ابتدا ثبت نام کنید.")
        return redirect("register")
    next_url = _safe_next(request, fallback="profile")
    if request.user.club_profile.is_gold_verified:
        return redirect(next_url)
    if BlueTickRequest.objects.filter(user=request.user, is_reviewed=False).exists():
        messages.success(request, GOLD_TICK_WAIT_MESSAGE)
        return redirect(next_url)
    full_name = (request.POST.get("full_name") or "").strip()[:80]
    phone = (request.POST.get("phone") or "").strip()[:20]
    biography = (request.POST.get("biography") or "").strip()[:2000]
    if not full_name or not phone or not biography:
        messages.error(request, "نام و نام خانوادگی، شماره تماس و رزومه را کامل کنید.")
        return redirect(next_url)
    BlueTickRequest.objects.create(
        user=request.user,
        full_name=full_name,
        phone=phone,
        biography=biography,
    )
    messages.success(request, GOLD_TICK_WAIT_MESSAGE)
    return redirect(next_url)


def request_blue_tick(request):
    return request_gold_tick(request)
