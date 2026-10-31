import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from banners.gmail import (
    google_authorize_url,
    google_fetch_profile,
    google_oauth_enabled,
    is_gmail_address,
    pop_valid_gmail_challenge,
    store_gmail_challenge,
)
from banners.images import optimize_profile_photo
from banners.accounts import SimpleClubRegisterForm, user_is_blocked
from banners.models import (
    BLUE_TICK_REJECTED_MESSAGE,
    BLUE_TICK_WAIT_MESSAGE,
    BlueTickRequest,
    UserProfile,
)


def _safe_next(request, fallback="profile"):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url.startswith("/") and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return reverse(fallback)


def _unique_username(base):
    base = (base or "player").strip()[:30] or "player"
    candidate = base
    index = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base[:24]}{index}"
        index += 1
    return candidate


def _login_user(request, user):
    if user_is_blocked(user):
        raise ValidationError("این اکانت مسدود شده است.")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")


def _get_or_create_user_for_gmail(email, google_sub=""):
    email = email.strip().lower()
    profile = UserProfile.objects.filter(google_email=email).select_related("user").first()
    if google_sub:
        by_sub = UserProfile.objects.filter(google_sub=google_sub).select_related("user").first()
        if by_sub:
            profile = by_sub
    if profile:
        changed = []
        if email and profile.google_email != email:
            profile.google_email = email
            changed.append("google_email")
        if google_sub and profile.google_sub != google_sub:
            profile.google_sub = google_sub
            changed.append("google_sub")
        if changed:
            profile.save(update_fields=changed)
        user = profile.user
        if email and not user.email:
            user.email = email
            user.save(update_fields=["email"])
        return user
    by_email = User.objects.filter(email__iexact=email).first()
    if by_email:
        club = by_email.club_profile
        club.google_email = email
        if google_sub:
            club.google_sub = google_sub
        club.save(update_fields=["google_email", "google_sub"] if google_sub else ["google_email"])
        return by_email
    user = User(username=_unique_username(email.split("@")[0]), email=email)
    user.set_unusable_password()
    user.save()
    club = user.club_profile
    club.google_email = email
    if google_sub:
        club.google_sub = google_sub
    club.save(update_fields=["google_email", "google_sub"] if google_sub else ["google_email"])
    return user


def _link_gmail(user, email, google_sub=""):
    email = email.strip().lower()
    taken = UserProfile.objects.filter(google_email=email).exclude(user=user)
    if taken.exists():
        raise ValidationError("این جیمیل به حساب دیگری وصل است.")
    if google_sub:
        taken_sub = UserProfile.objects.filter(google_sub=google_sub).exclude(user=user)
        if taken_sub.exists():
            raise ValidationError("این حساب گوگل به کاربر دیگری وصل است.")
    profile = user.club_profile
    profile.google_email = email
    if google_sub:
        profile.google_sub = google_sub
    profile.save(update_fields=["google_email", "google_sub"] if google_sub else ["google_email"])
    if email and user.email != email:
        user.email = email
        user.save(update_fields=["email"])


def blue_tick_state(user):
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
    return {"pending_blue_tick": pending, "rejected_blue_tick": rejected}


def profile_page_context(request, extra=None):
    profile = request.user.club_profile if request.user.is_authenticated else None
    my_ads = []
    if request.user.is_authenticated:
        my_ads = list(request.user.event_ads.all().order_by("-created_at", "-id"))
    context = {
        "club_profile": profile,
        "my_ads": my_ads,
        "register_form": SimpleClubRegisterForm(),
        "show_auth_methods": False,
        "blue_tick_wait_message": BLUE_TICK_WAIT_MESSAGE,
        "blue_tick_rejected_message": BLUE_TICK_REJECTED_MESSAGE,
    }
    context.update(blue_tick_state(request.user))
    if extra:
        context.update(extra)
    return context


def profile_page(request):
    return render(request, "account/profile.html", profile_page_context(request))


@require_POST
def send_gmail_code(request):
    email = (request.POST.get("email") or "").strip().lower()
    purpose = "link" if request.user.is_authenticated else "recover"
    next_url = _safe_next(request)
    if not is_gmail_address(email):
        messages.error(request, "یک نشانی جیمیل معتبر وارد کنید.")
        return redirect(next_url)
    if request.user.is_authenticated:
        clash = UserProfile.objects.filter(google_email=email).exclude(user=request.user)
        if clash.exists():
            messages.error(request, "این جیمیل به حساب دیگری وصل است.")
            return redirect(next_url)
    code = store_gmail_challenge(request, email, purpose)
    if settings.DEBUG:
        messages.info(request, f"کد تایید برای تست: {code}")
    else:
        messages.success(request, "کد تایید به جیمیل شما ارسال شد.")
    request.session["gmail_pending_email"] = email
    request.session.modified = True
    return redirect(next_url)


@require_POST
def verify_gmail_code(request):
    email = (request.POST.get("email") or request.session.get("gmail_pending_email") or "").strip().lower()
    code = (request.POST.get("code") or "").strip()
    purpose = "link" if request.user.is_authenticated else "recover"
    next_url = _safe_next(request)
    if not pop_valid_gmail_challenge(request, email, code, purpose):
        messages.error(request, "کد تایید نادرست یا منقضی است.")
        return redirect(next_url)
    try:
        if request.user.is_authenticated:
            _link_gmail(request.user, email)
            messages.success(request, "جیمیل به حساب شما وصل شد.")
        else:
            user = _get_or_create_user_for_gmail(email)
            _login_user(request, user)
            messages.success(request, "با جیمیل وارد شدید.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    request.session.pop("gmail_pending_email", None)
    return redirect(next_url)


@require_GET
def google_start(request):
    if not google_oauth_enabled():
        messages.error(request, "اتصال یک‌کلیکی جیمیل هنوز روی سرور تنظیم نشده است.")
        return redirect("profile")
    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_next"] = _safe_next(request)
    request.session.modified = True
    redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI or request.build_absolute_uri(reverse("google_callback"))
    return redirect(google_authorize_url(redirect_uri, state))


@require_GET
def google_callback(request):
    next_url = request.session.pop("google_oauth_next", None) or reverse("profile")
    expected = request.session.pop("google_oauth_state", "")
    state = request.GET.get("state") or ""
    code = request.GET.get("code") or ""
    if not expected or state != expected or not code:
        messages.error(request, "اتصال به گوگل کامل نشد.")
        return redirect(next_url)
    redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI or request.build_absolute_uri(reverse("google_callback"))
    info = google_fetch_profile(code, redirect_uri)
    email = ((info or {}).get("email") or "").strip().lower()
    sub = ((info or {}).get("sub") or "").strip()
    if not info or not email or not is_gmail_address(email):
        messages.error(request, "فقط حساب جیمیل برای اتصال پذیرفته می‌شود.")
        return redirect(next_url)
    try:
        if request.user.is_authenticated:
            _link_gmail(request.user, email, google_sub=sub)
            messages.success(request, "جیمیل به حساب شما وصل شد.")
        else:
            user = _get_or_create_user_for_gmail(email, google_sub=sub)
            _login_user(request, user)
            messages.success(request, "با جیمیل وارد شدید.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect(next_url)


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
def request_blue_tick(request):
    if not request.user.is_authenticated:
        messages.error(request, "برای درخواست تیک آبی ابتدا ثبت نام کنید.")
        return redirect("register")
    next_url = _safe_next(request, fallback="profile")
    if request.user.club_profile.is_verified:
        return redirect(next_url)
    if BlueTickRequest.objects.filter(user=request.user, is_reviewed=False).exists():
        messages.success(request, BLUE_TICK_WAIT_MESSAGE)
        return redirect(next_url)
    full_name = (request.POST.get("full_name") or "").strip()[:80]
    phone = (request.POST.get("phone") or "").strip()[:20]
    biography = (request.POST.get("biography") or "").strip()[:2000]
    if not full_name or not phone or not biography:
        messages.error(request, "نام و نام خانوادگی، شماره تماس و بیوگرافی را کامل کنید.")
        return redirect(next_url)
    BlueTickRequest.objects.create(
        user=request.user,
        full_name=full_name,
        phone=phone,
        biography=biography,
    )
    messages.success(request, BLUE_TICK_WAIT_MESSAGE)
    return redirect(next_url)
