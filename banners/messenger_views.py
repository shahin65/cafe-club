import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from banners.accounts import user_is_blocked
from banners.messenger_link import (
    OTP_TTL,
    consume_login_code,
    create_link_token,
    create_signup_ticket,
    deep_link as messenger_deep_link,
    mask_mobile,
    ticket_state as messenger_ticket_state,
)
from banners.models import UserProfile
from banners.telegram import telegram_bot_ready, telegram_public_context, ticket_state, verify_webhook_request
from banners import bale as bale_bot
from banners import telegram as telegram_bot
from banners.bale import bale_bot_ready, bale_public_context, verify_webhook_request as verify_bale_webhook

AUTH_SIGNUP_MESSAGE = "ثبت‌نام شما انجام شد."


def _wants_json(request):
    accept = request.headers.get("Accept", "")
    content_type = request.content_type or ""
    return (
        "application/json" in accept
        or "application/json" in content_type
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def _json_body(request):
    try:
        raw = request.body.decode("utf-8") if request.body else ""
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _request_payload(request):
    if request.content_type and "application/json" in request.content_type:
        return _json_body(request)
    return request.POST


def _login_user(request, user):
    if user_is_blocked(user):
        return False
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return True


def admit_club_member(request, phone: str, *, telegram_chat_id="", bale_chat_id=""):
    phone = str(phone or "").strip()
    telegram_id = str(telegram_chat_id or "").strip()
    bale_id = str(bale_chat_id or "").strip()
    profile = None
    if telegram_id:
        profile = UserProfile.objects.filter(telegram_chat_id=telegram_id).select_related("user").first()
    if not profile and bale_id:
        profile = UserProfile.objects.filter(bale_chat_id=bale_id).select_related("user").first()
    if not profile and phone:
        profile = UserProfile.objects.filter(mobile=phone).select_related("user").first()
    created = False
    if profile:
        user = profile.user
    else:
        username = phone or f"tg{telegram_id or bale_id}"
        user, created = User.objects.get_or_create(username=username, defaults={"email": ""})
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        profile = user.club_profile
    fields = []
    if phone and profile.mobile != phone:
        clash = UserProfile.objects.filter(mobile=phone).exclude(pk=profile.pk).exists()
        if not clash:
            profile.mobile = phone
            fields.append("mobile")
    if telegram_id and not profile.telegram_chat_id:
        clash = UserProfile.objects.filter(telegram_chat_id=telegram_id).exclude(pk=profile.pk).exists()
        if not clash:
            profile.telegram_chat_id = telegram_id
            fields.append("telegram_chat_id")
    if bale_id and not profile.bale_chat_id:
        clash = UserProfile.objects.filter(bale_chat_id=bale_id).exclude(pk=profile.pk).exists()
        if not clash:
            profile.bale_chat_id = bale_id
            fields.append("bale_chat_id")
    if phone and not profile.is_verified:
        profile.is_verified = True
        fields.append("is_verified")
    guest_name = (request.session.get("profile_display_name") or "").strip()[:40]
    if guest_name and not (profile.display_name or "").strip():
        profile.display_name = guest_name
        fields.append("display_name")
    try:
        guest_changes = int(request.session.get("display_name_changes") or 0)
    except (TypeError, ValueError):
        guest_changes = 0
    if guest_changes > (profile.display_name_changes or 0):
        profile.display_name_changes = guest_changes
        fields.append("display_name_changes")
    if fields:
        profile.save(update_fields=fields)
    if not _login_user(request, user):
        return None
    return user


@require_POST
def telegram_start(request):
    if request.user.is_authenticated:
        if not telegram_bot_ready():
            return JsonResponse(
                {"success": False, "message": "اتصال تلگرام هنوز فعال نیست."},
                status=503,
            )
        token = create_link_token(request.user, "telegram")
        request.session["telegram_link_token"] = token
        return JsonResponse(
            {
                "success": True,
                "mode": "link",
                "url": messenger_deep_link("telegram", token),
                "ttl": OTP_TTL,
                "message": "در تلگرام استارت را بزن تا حساب کافه کلاب وصل شود.",
            }
        )
    context = telegram_public_context()
    if not context["enabled"]:
        return JsonResponse(
            {"success": False, "message": "ثبت‌نام تلگرام هنوز فعال نیست. توکن ربات را روی سرور بگذار."},
            status=503,
        )
    ticket = create_signup_ticket("telegram")
    request.session["telegram_ticket"] = ticket
    return JsonResponse(
        {
            "success": True,
            "mode": "signup",
            "url": messenger_deep_link("telegram", ticket),
            "ttl": OTP_TTL,
            "message": "در تلگرام استارت را بزن، شماره را بفرست و کد را در سایت وارد کن.",
        }
    )


@require_GET
def telegram_status(request):
    if request.user.is_authenticated:
        token = request.session.get("telegram_link_token") or ""
        profile = getattr(request.user, "club_profile", None)
        if profile and profile.telegram_chat_id:
            request.session.pop("telegram_link_token", None)
            return JsonResponse(
                {
                    "success": True,
                    "mode": "link",
                    "message": "حساب تلگرام به کافه کلاب متصل شد.",
                }
            )
        if token and not messenger_ticket_state(token):
            request.session.pop("telegram_link_token", None)
            return JsonResponse(
                {
                    "success": False,
                    "pending": False,
                    "message": "لینک اتصال منقضی شد. دوباره تلاش کن.",
                }
            )
        return JsonResponse(
            {"success": False, "pending": True, "message": "در انتظار تایید تلگرام…"}
        )
    ticket = request.session.get("telegram_ticket") or ""
    state = ticket_state(ticket)
    if not state:
        return JsonResponse(
            {"success": False, "pending": True, "message": "در انتظار تایید تلگرام…"}
        )
    if state.get("status") == "code_sent":
        return JsonResponse(
            {
                "success": False,
                "pending": True,
                "awaiting_code": True,
                "ttl": OTP_TTL,
                "message": "کد تایید تلگرام را در سایت وارد کن.",
            }
        )
    return JsonResponse(
        {
            "success": False,
            "pending": True,
            "message": "در تلگرام استارت را بزن و شماره را به اشتراک بگذار.",
        }
    )


@require_POST
def bale_start(request):
    if request.user.is_authenticated:
        if not bale_bot_ready():
            return JsonResponse(
                {"success": False, "message": "اتصال بله هنوز فعال نیست."},
                status=503,
            )
        token = create_link_token(request.user, "bale")
        request.session["bale_link_token"] = token
        return JsonResponse(
            {
                "success": True,
                "mode": "link",
                "url": messenger_deep_link("bale", token),
                "ttl": OTP_TTL,
                "message": "در بله استارت را بزن تا حساب کافه کلاب وصل شود.",
            }
        )
    context = bale_public_context()
    if not context["enabled"]:
        return JsonResponse(
            {"success": False, "message": "ثبت‌نام بله هنوز فعال نیست. توکن ربات را روی سرور بگذار."},
            status=503,
        )
    ticket = create_signup_ticket("bale")
    request.session["bale_ticket"] = ticket
    return JsonResponse(
        {
            "success": True,
            "mode": "signup",
            "url": messenger_deep_link("bale", ticket),
            "ttl": OTP_TTL,
            "message": "در بله استارت را بزن، شماره را بفرست و کد را در سایت وارد کن.",
        }
    )


@require_GET
def bale_status(request):
    if request.user.is_authenticated:
        token = request.session.get("bale_link_token") or ""
        profile = getattr(request.user, "club_profile", None)
        if profile and profile.bale_chat_id:
            request.session.pop("bale_link_token", None)
            return JsonResponse(
                {
                    "success": True,
                    "mode": "link",
                    "message": "حساب بله به کافه کلاب متصل شد.",
                }
            )
        if token and not messenger_ticket_state(token):
            request.session.pop("bale_link_token", None)
            return JsonResponse(
                {
                    "success": False,
                    "pending": False,
                    "message": "لینک اتصال منقضی شد. دوباره تلاش کن.",
                }
            )
        return JsonResponse(
            {"success": False, "pending": True, "message": "در انتظار تایید بله…"}
        )
    ticket = request.session.get("bale_ticket") or ""
    state = bale_bot.ticket_state(ticket)
    if not state:
        return JsonResponse(
            {"success": False, "pending": True, "message": "در انتظار تایید بله…"}
        )
    if state.get("status") == "code_sent":
        return JsonResponse(
            {
                "success": False,
                "pending": True,
                "awaiting_code": True,
                "ttl": OTP_TTL,
                "message": "کد تایید بله را در سایت وارد کن.",
            }
        )
    return JsonResponse(
        {
            "success": False,
            "pending": True,
            "message": "در بله استارت را بزن و شماره را به اشتراک بگذار.",
        }
    )


@require_POST
def messenger_verify_code(request):
    wants_json = _wants_json(request)
    profile_url = reverse("profile")
    if request.user.is_authenticated:
        if wants_json:
            return JsonResponse(
                {
                    "success": False,
                    "message": "قبلاً وارد حساب شده‌ای.",
                    "redirect": profile_url,
                },
                status=400,
            )
        return redirect("profile")
    payload = _request_payload(request)
    if payload is None:
        if wants_json:
            return JsonResponse({"success": False, "message": "بدنهٔ درخواست نامعتبر است."}, status=400)
        messages.error(request, "بدنهٔ درخواست نامعتبر است.")
        return redirect("profile")
    ticket = request.session.get("telegram_ticket") or request.session.get("bale_ticket") or ""
    result = consume_login_code(
        str(payload.get("code") or ""),
        ticket=str(ticket),
        ip=request.META.get("REMOTE_ADDR", ""),
    )
    if not result.get("ok"):
        message = result.get("message") or "کد نامعتبر است."
        status = int(result.get("status") or 400)
        if wants_json:
            return JsonResponse({"success": False, "message": message}, status=status)
        messages.error(request, message)
        return redirect("profile")
    kwargs = {}
    if result.get("platform") == "telegram":
        kwargs["telegram_chat_id"] = str(result.get("chat_id") or "")
    elif result.get("platform") == "bale":
        kwargs["bale_chat_id"] = str(result.get("chat_id") or "")
    phone = str(result["phone"])
    user = admit_club_member(request, phone, **kwargs)
    if user is None:
        message = "این اکانت مسدود شده است."
        if wants_json:
            return JsonResponse({"success": False, "message": message}, status=403)
        messages.error(request, message)
        return redirect("profile")
    request.session.pop("telegram_ticket", None)
    request.session.pop("bale_ticket", None)
    masked = mask_mobile(phone)
    message = f"{AUTH_SIGNUP_MESSAGE} · {masked}" if masked else AUTH_SIGNUP_MESSAGE
    messages.success(request, message)
    if wants_json:
        return JsonResponse({"success": True, "message": message, "redirect": profile_url})
    return redirect("profile")


@csrf_exempt
@require_POST
def telegram_webhook(request, secret: str = ""):
    if not verify_webhook_request(request, url_secret=secret):
        return HttpResponse(status=403)
    payload = _json_body(request) or {}
    telegram_bot.handle_update(payload)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def bale_webhook(request, secret: str = ""):
    if not verify_bale_webhook(url_secret=secret):
        return HttpResponse(status=403)
    payload = _json_body(request) or {}
    bale_bot.handle_update(payload)
    return JsonResponse({"ok": True})
