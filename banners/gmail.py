import hashlib
import hmac
import json
import random
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

GMAIL_SESSION_KEY = "gmail_verify"
CODE_MINUTES = 10
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


def make_gmail_code():
    return f"{random.randint(100000, 999999)}"


def is_gmail_address(value):
    email = (value or "").strip().lower()
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1]
    return domain in GMAIL_DOMAINS


def hash_code(code):
    return hmac.new(settings.SECRET_KEY.encode(), str(code).encode(), hashlib.sha256).hexdigest()


def store_gmail_challenge(request, email, purpose):
    code = make_gmail_code()
    request.session[GMAIL_SESSION_KEY] = {
        "email": email.strip().lower(),
        "purpose": purpose,
        "digest": hash_code(code),
        "expires": (timezone.now() + timedelta(minutes=CODE_MINUTES)).isoformat(),
    }
    request.session.modified = True
    send_mail(
        "کد تایید کافه کلاب",
        f"کد تایید جیمیل شما: {code}",
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=True,
    )
    return code


def pop_valid_gmail_challenge(request, email, code, purpose):
    payload = request.session.get(GMAIL_SESSION_KEY) or {}
    if not payload:
        return False
    expires = payload.get("expires")
    try:
        expiry = datetime.fromisoformat(expires)
        if timezone.is_naive(expiry):
            expiry = timezone.make_aware(expiry, timezone.get_current_timezone())
    except (TypeError, ValueError):
        return False
    if timezone.now() > expiry:
        request.session.pop(GMAIL_SESSION_KEY, None)
        return False
    ok = (
        payload.get("email") == (email or "").strip().lower()
        and payload.get("purpose") == purpose
        and hmac.compare_digest(payload.get("digest") or "", hash_code(code))
    )
    if ok:
        request.session.pop(GMAIL_SESSION_KEY, None)
    return ok


def google_oauth_enabled():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def google_authorize_url(redirect_uri, state):
    query = urllib.parse.urlencode(
        {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "prompt": "select_account",
            "state": state,
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def google_fetch_profile(code, redirect_uri):
    token_body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()
    token_request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(token_request, timeout=15) as response:
            tokens = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    access = tokens.get("access_token")
    if not access:
        return None
    info_request = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access}"},
    )
    try:
        with urllib.request.urlopen(info_request, timeout=15) as response:
            return json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return None
