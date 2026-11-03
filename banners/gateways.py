import base64
import json
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.db import transaction

from banners.app_source import normalize_source


class GatewayError(Exception):
    pass


class GatewayHttpError(GatewayError):
    def __init__(self, status, body):
        self.status = status
        self.body = body or ""
        parsed = _json_body(self.body)
        self.error_code = str(parsed.get("error") or "")
        super().__init__(_public_gateway_error(parsed, self.body))


def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _redact(text):
    secrets = [
        getattr(settings, "BITPAY_API_KEY", ""),
        getattr(settings, "BAZAAR_CLIENT_SECRET", ""),
        getattr(settings, "BAZAAR_REFRESH_TOKEN", ""),
        getattr(settings, "MYKET_ACCESS_TOKEN", ""),
    ]
    out = str(text or "")
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[redacted]")
    return out[:240]


def _request(url, *, data=None, headers=None, method=None, timeout=20):
    body = None
    req_headers = {"User-Agent": "CafeClub/1.0", "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if data is not None:
        if isinstance(data, dict) and req_headers.get("Content-Type") == "application/json":
            body = json.dumps(data).encode("utf-8")
        elif isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif isinstance(data, (bytes, bytearray)):
            body = data
        else:
            body = str(data).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=req_headers, method=method or ("POST" if body else "GET"))
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise GatewayHttpError(exc.code, raw or f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise GatewayError(_redact(getattr(exc, "reason", exc))) from exc
    return status, raw


def _json_body(raw):
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def _secret(name):
    return str(getattr(settings, name, "") or "").strip().strip("'").strip('"')


def _public_gateway_error(parsed, raw=""):
    code = str((parsed or {}).get("error") or "").lower()
    if code in {"invalid_grant", "invalid_token"}:
        return "توکن API کافه بازار نامعتبر است. از پیشخوان بازار یک refresh_token تازه بگیرید."
    if code == "invalid_client":
        return "شناسه یا رمز کلاینت کافه بازار نادرست است."
    if code in {"invalid_credentials", "unauthorized"}:
        return "دسترسی API کافه بازار رد شد."
    text = str((parsed or {}).get("error_description") or raw or "").strip()
    lowered = text.lower()
    if "invalid_grant" in lowered or "invalid grant" in lowered:
        return "توکن API کافه بازار نامعتبر است. از پیشخوان بازار یک refresh_token تازه بگیرید."
    return _redact(text) or "ارتباط با درگاه برقرار نشد."


def gateway_for_source(source):
    source = normalize_source(source) or "direct"
    if source == "bazaar":
        return "bazaar"
    if source == "myket":
        return "myket"
    return "bitpay"


def toman_to_rial(amount_toman):
    return int(amount_toman) * 10


def bitpay_configured():
    return bool(getattr(settings, "BITPAY_API_KEY", ""))


def _bitpay_urls():
    if getattr(settings, "BITPAY_SANDBOX", False):
        return (
            "https://bitpay.ir/payment-test/gateway-send",
            "https://bitpay.ir/payment-test/gateway-result-second",
            "https://bitpay.ir/payment-test/gateway-{id_get}-get",
        )
    return (
        "https://bitpay.ir/payment/gateway-send",
        "https://bitpay.ir/payment/gateway-result-second",
        "https://bitpay.ir/payment/gateway-{id_get}-get",
    )


def bitpay_request(amount_toman, order_id, callback_url, name="", email="", description=""):
    if not bitpay_configured():
        raise GatewayError("کلید بیت‌پی روی سرور تنظیم نشده است.")
    send_url, _, pay_url = _bitpay_urls()
    _status, raw = _request(
        send_url,
        data={
            "api": settings.BITPAY_API_KEY,
            "redirect": callback_url,
            "amount": str(toman_to_rial(amount_toman)),
            "factorId": str(order_id),
            "name": name or "",
            "email": email or "",
            "description": description or "پرداخت کافه کلاب",
        },
    )
    token = (raw or "").strip()
    try:
        id_get = int(token)
    except ValueError:
        raise GatewayError(_redact(token) or "پاسخ درگاه بیت‌پی نامعتبر است.") from None
    if id_get <= 0:
        raise GatewayError(f"خطای درگاه بیت‌پی ({id_get}).")
    return str(id_get), pay_url.format(id_get=id_get)


def bitpay_verify(trans_id, id_get):
    if not bitpay_configured():
        raise GatewayError("کلید بیت‌پی روی سرور تنظیم نشده است.")
    _, verify_url, _ = _bitpay_urls()
    _status, raw = _request(
        verify_url,
        data={
            "api": settings.BITPAY_API_KEY,
            "trans_id": str(trans_id),
            "id_get": str(id_get),
            "json": "1",
        },
    )
    data = _json_body(raw)
    if not data:
        raise GatewayError(_redact(raw) or "پاسخ تایید بیت‌پی نامعتبر است.")
    status = data.get("status")
    if str(status) != "1":
        raise GatewayError("پرداخت بیت‌پی تایید نشد.")
    return data


def bazaar_oauth_configured():
    return bool(_secret("BAZAAR_CLIENT_ID") and _secret("BAZAAR_CLIENT_SECRET") and _bazaar_refresh_token())


def bazaar_configured():
    return bazaar_oauth_configured() or bool(_secret("BAZAAR_RSA"))


_bazaar_token = {"access": "", "expires": 0.0}
_bazaar_lock = threading.Lock()


def _bazaar_refresh_token():
    stored = ""
    try:
        from banners.models import SiteSettings

        stored = (SiteSettings.load().bazaar_refresh_token or "").strip()
    except Exception:
        stored = ""
    return stored or _secret("BAZAAR_REFRESH_TOKEN")


def _store_bazaar_refresh_token(token):
    token = (token or "").strip()
    if not token or token == _bazaar_refresh_token():
        return
    from banners.models import SiteSettings

    with transaction.atomic():
        SiteSettings.objects.get_or_create(pk=1)
        row = SiteSettings.objects.select_for_update().get(pk=1)
        if row.bazaar_refresh_token == token:
            return
        row.bazaar_refresh_token = token
        row.save(update_fields=["bazaar_refresh_token"])


def bazaar_access_token():
    if not bazaar_oauth_configured():
        raise GatewayError("اطلاعات API کافه بازار روی سرور تنظیم نشده است.")
    now = time.time()
    if _bazaar_token["access"] and _bazaar_token["expires"] > now + 30:
        return _bazaar_token["access"]
    with _bazaar_lock:
        now = time.time()
        if _bazaar_token["access"] and _bazaar_token["expires"] > now + 30:
            return _bazaar_token["access"]
        payload = {
            "grant_type": "refresh_token",
            "client_id": _secret("BAZAAR_CLIENT_ID"),
            "client_secret": _secret("BAZAAR_CLIENT_SECRET"),
            "refresh_token": _bazaar_refresh_token(),
        }
        redirect_uri = _secret("BAZAAR_REDIRECT_URI")
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri
        try:
            _status, raw = _request("https://pardakht.cafebazaar.ir/devapi/v2/auth/token/", data=payload)
        except GatewayHttpError as exc:
            _bazaar_token["access"] = ""
            raise GatewayError(_public_gateway_error({"error": exc.error_code}, exc.body)) from exc
        data = _json_body(raw)
        token = data.get("access_token")
        if not token:
            raise GatewayError(_public_gateway_error(data, raw))
        rotated = (data.get("refresh_token") or "").strip()
        if rotated:
            _store_bazaar_refresh_token(rotated)
        _bazaar_token["access"] = token
        _bazaar_token["expires"] = now + int(data.get("expires_in") or 3600)
        return token


def _bazaar_validate(sku, purchase_token, access_token):
    package_name = _secret("ANDROID_PACKAGE_NAME") or "ir.cafeclub.amytis"
    url = (
        "https://pardakht.cafebazaar.ir/devapi/v2/api/validate/"
        f"{urllib.parse.quote(package_name)}/inapp/{urllib.parse.quote(sku)}"
        f"/purchases/{urllib.parse.quote(purchase_token)}/?access_token={urllib.parse.quote(access_token)}"
    )
    _status, raw = _request(url, headers={"Authorization": f"Bearer {access_token}"})
    data = _json_body(raw)
    if str(data.get("purchaseState")) != "0":
        raise GatewayError("خرید کافه بازار معتبر نیست.")
    return data


def _bazaar_verify_signature(sku, purchase_token, original_json, signature):
    rsa_b64 = "".join(_secret("BAZAAR_RSA").split())
    if not rsa_b64 or not original_json or not signature:
        return None
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import load_der_public_key
    except ImportError as exc:
        raise GatewayError("کتابخانه تأیید امضای کافه بازار روی سرور نصب نیست.") from exc
    try:
        public_key = load_der_public_key(base64.b64decode(rsa_b64))
        public_key.verify(
            base64.b64decode("".join(signature.split())),
            original_json.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA1(),
        )
        data = json.loads(original_json)
    except Exception as exc:
        raise GatewayError("امضای خرید کافه بازار معتبر نیست.") from exc
    package_name = _secret("ANDROID_PACKAGE_NAME") or "ir.cafeclub.amytis"
    if str(data.get("productId") or "") != str(sku):
        raise GatewayError("شناسه محصول خرید با بسته هم‌خوانی ندارد.")
    if str(data.get("purchaseToken") or "") != str(purchase_token):
        raise GatewayError("توکن خرید کافه بازار هم‌خوانی ندارد.")
    if str(data.get("packageName") or "") and str(data.get("packageName")) != package_name:
        raise GatewayError("پکیج‌نیم خرید با برنامه هم‌خوانی ندارد.")
    if str(data.get("purchaseState", "0")) not in {"0", "PURCHASED"}:
        raise GatewayError("خرید کافه بازار معتبر نیست.")
    return data


def bazaar_verify(sku, purchase_token, original_json="", signature=""):
    signed = None
    oauth_error = None
    if bazaar_oauth_configured():
        try:
            token = bazaar_access_token()
            try:
                return _bazaar_validate(sku, purchase_token, token)
            except GatewayHttpError as exc:
                if exc.status in {401, 403}:
                    _bazaar_token["access"] = ""
                    token = bazaar_access_token()
                    return _bazaar_validate(sku, purchase_token, token)
                raise
        except GatewayError as exc:
            oauth_error = exc
    try:
        signed = _bazaar_verify_signature(sku, purchase_token, original_json, signature)
    except GatewayError:
        signed = None
        if oauth_error is None:
            raise
    if signed is not None:
        return signed
    if oauth_error:
        raise oauth_error
    raise GatewayError("اطلاعات API کافه بازار روی سرور تنظیم نشده است.")


def myket_configured():
    return bool(getattr(settings, "MYKET_ACCESS_TOKEN", ""))


def myket_verify(sku, purchase_token):
    if not myket_configured():
        raise GatewayError("توکن مایکت روی سرور تنظیم نشده است.")
    package_name = getattr(settings, "ANDROID_PACKAGE_NAME", "") or "ir.cafeclub.amytis"
    url = (
        "https://developer.myket.ir/api/partners/applications/"
        f"{urllib.parse.quote(package_name)}/purchases/products/{urllib.parse.quote(sku)}/verify"
    )
    _status, raw = _request(
        url,
        data={"tokenId": purchase_token},
        headers={
            "X-Access-Token": settings.MYKET_ACCESS_TOKEN,
            "Content-Type": "application/json",
        },
    )
    data = _json_body(raw)
    if str(data.get("purchaseState")) != "0":
        raise GatewayError("خرید مایکت معتبر نیست.")
    return data
