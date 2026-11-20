"""Bale bot: share-contact signup. Token never leaves the server."""
from __future__ import annotations

import hmac
import json
import logging
import ssl
import threading
import time
import urllib.error
import urllib.request

from django.conf import settings

from banners.messenger_link import (
    bind_signup_chat,
    code_message,
    complete_signup,
    create_signup_ticket,
    deep_link as make_deep_link,
    normalize_mobile,
    resolve_start_link,
    signup_token_for_chat,
    start_payload,
    ticket_state as shared_ticket_state,
)

logger = logging.getLogger(__name__)

BALE_ORIGIN = "https://tapi.bale.ai"
START_TEXT = (
    "به ربات ثبت‌نام کافه کلاب خوش آمدی.\n\n"
    "برای تکمیل ثبت‌نام، شماره موبایلی که روی همین حساب بله ثبت شده را به اشتراک بگذار."
)
SHARE_BUTTON = "اشتراک‌گذاری شماره موبایل بله"
OWN_CONTACT_ONLY = (
    "فقط شمارهٔ همین حساب بله پذیرفته می‌شود. "
    "از دکمهٔ اشتراک‌گذاری شماره استفاده کن، نه ارسال مخاطب دیگران."
)
NEED_SITE = "برای شروع ثبت‌نام، از دکمهٔ بله در سایت کافه کلاب وارد این بازو شو."

_poller_lock = threading.Lock()
_poller_started = False


def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def bale_auth_token() -> str:
    dedicated = str(getattr(settings, "BALE_AUTH_BOT_TOKEN", "") or "")
    if dedicated:
        return dedicated
    return str(getattr(settings, "BALE_BOT_TOKEN", "") or "")


def bale_bot_ready() -> bool:
    username = str(getattr(settings, "BALE_BOT_USERNAME", "") or "").lstrip("@")
    return bool(bale_auth_token() and username)


def bale_public_context() -> dict:
    username = str(getattr(settings, "BALE_BOT_USERNAME", "") or "").lstrip("@")
    ready = bale_bot_ready()
    return {
        "enabled": ready,
        "link_enabled": ready,
        "username": username,
        "deep_link": f"https://ble.ir/{username}" if username else "",
    }


def create_ticket() -> str:
    return create_signup_ticket("bale")


def deep_link(ticket: str) -> str:
    return make_deep_link("bale", ticket)


def ticket_state(ticket: str) -> dict | None:
    return shared_ticket_state(ticket)


def handle_update(update: dict) -> None:
    message = (update or {}).get("message") or {}
    if not message:
        return
    chat_id = (message.get("chat") or {}).get("id")
    from_user = message.get("from") or {}
    from_id = from_user.get("id")
    text = str(message.get("text") or "").strip()
    contact = message.get("contact")
    if chat_id is None:
        return
    if text.startswith("/start"):
        _on_start(chat_id, text)
        return
    if contact:
        _on_contact(chat_id, from_id, contact)


def public_site_url() -> str:
    return str(getattr(settings, "PUBLIC_SITE_URL", "") or "").strip().rstrip("/")


def webhook_url() -> str:
    return str(getattr(settings, "BALE_WEBHOOK_URL", "") or "").strip()



def webhook_secret() -> str:
    return str(getattr(settings, "BALE_WEBHOOK_SECRET", "") or "")


def verify_webhook_request(url_secret: str = "") -> bool:
    expected = webhook_secret()
    if not expected or not url_secret:
        return False
    return hmac.compare_digest(str(url_secret), expected)


def api(method: str, payload: dict | None = None) -> dict:
    token = bale_auth_token()
    if not token:
        return {"ok": False, "description": "Bale token is not configured."}
    url = f"{BALE_ORIGIN}/bot{token}/{method}"
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "CafeClubBale/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30, context=_ssl_context()) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Bale HTTP error %s", exc.code)
            return {"ok": False, "error_code": exc.code, "description": "Bale HTTP error"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        logger.warning("Bale API call failed")
        return {"ok": False, "description": "Bale unreachable"}


def start_poller() -> None:
    global _poller_started
    with _poller_lock:
        if _poller_started:
            return
        if not bale_bot_ready():
            return
        using_webhook = bool(webhook_url())
        _poller_started = True
    configure_bot()
    if using_webhook:
        return
    thread = threading.Thread(target=_poll_loop, name="bale-poller", daemon=True)
    thread.start()


def _poll_loop() -> None:
    offset = 0
    while True:
        result = api("getUpdates", {"offset": offset, "timeout": 25, "limit": 50})
        if not result.get("ok"):
            time.sleep(3)
            continue
        for update in result.get("result") or []:
            try:
                handle_update(update)
            except Exception:
                logger.exception("Bale update handling failed")
            try:
                offset = int(update.get("update_id", offset)) + 1
            except (TypeError, ValueError):
                continue


def _on_start(chat_id, text: str) -> None:
    token = start_payload(text)
    linked = resolve_start_link(token=token, chat_id=chat_id, platform="bale")
    if linked is not None:
        api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": linked.get("message") or NEED_SITE,
                "reply_markup": {"remove_keyboard": True},
            },
        )
        return
    state = ticket_state(token)
    if state and state.get("status") == "pending":
        bind_signup_chat(token, chat_id, "bale")
        _ask_contact(chat_id, START_TEXT)
        return
    ticket = signup_token_for_chat("bale", chat_id)
    if ticket and ticket_state(ticket):
        _ask_contact(chat_id, START_TEXT)
        return
    api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": NEED_SITE,
            "reply_markup": {"remove_keyboard": True},
        },
    )


def _on_contact(chat_id, from_id, contact: dict) -> None:
    contact_user = contact.get("user_id")
    try:
        own = int(contact_user) == int(from_id)
    except (TypeError, ValueError):
        own = False
    if not own:
        api(
            "sendMessage",
            {"chat_id": chat_id, "text": OWN_CONTACT_ONLY, "reply_markup": _contact_keyboard()},
        )
        return
    phone = normalize_mobile(str(contact.get("phone_number") or ""))
    if not phone:
        api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "شماره موبایل بله قابل تایید نبود. دوباره اشتراک بگذار.",
                "reply_markup": _contact_keyboard(),
            },
        )
        return
    state, code = complete_signup(
        chat_id,
        "bale",
        phone=phone,
        messenger_user_id=from_id,
    )
    if not state or not code:
        api("sendMessage", {"chat_id": chat_id, "text": NEED_SITE})
        return
    api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": code_message(code),
            "parse_mode": "HTML",
            "reply_markup": {"remove_keyboard": True},
        },
    )


def _ask_contact(chat_id, text: str) -> None:
    api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": _contact_keyboard(),
        },
    )


def _contact_keyboard() -> dict:
    return {
        "keyboard": [[{"text": SHARE_BUTTON, "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def set_webhook(url: str = "") -> dict:
    target = (url or webhook_url()).strip()
    if not target:
        return {"ok": False, "description": "Webhook URL is not configured."}
    return api(
        "setWebhook",
        {
            "url": target,
            "drop_pending_updates": True,
        },
    )


def delete_webhook() -> dict:
    return api("deleteWebhook", {"drop_pending_updates": True})


def configure_bot() -> None:
    api(
        "setMyCommands",
        {"commands": [{"command": "start", "description": "شروع ثبت‌نام کافه کلاب"}]},
    )
    if webhook_url():
        set_webhook()
    else:
        delete_webhook()
