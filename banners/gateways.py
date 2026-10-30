import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from banners.app_source import normalize_source


class GatewayError(Exception):
    pass


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
        raise GatewayError(_redact(raw or f"HTTP {exc.code}")) from exc
    except urllib.error.URLError as exc:
        raise GatewayError(_redact(getattr(exc, "reason", exc))) from exc
    return status, raw


def _json_body(raw):
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


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


def bazaar_configured():
    return bool(
        getattr(settings, "BAZAAR_CLIENT_ID", "")
        and getattr(settings, "BAZAAR_CLIENT_SECRET", "")
        and getattr(settings, "BAZAAR_REFRESH_TOKEN", "")
    )


_bazaar_token = {"access": "", "expires": 0.0}


def bazaar_access_token():
    if not bazaar_configured():
        raise GatewayError("اطلاعات API کافه بازار روی سرور تنظیم نشده است.")
    now = time.time()
    if _bazaar_token["access"] and _bazaar_token["expires"] > now + 30:
        return _bazaar_token["access"]
    _status, raw = _request(
        "https://pardakht.cafebazaar.ir/devapi/v2/auth/token/",
        data={
            "grant_type": "refresh_token",
            "client_id": settings.BAZAAR_CLIENT_ID,
            "client_secret": settings.BAZAAR_CLIENT_SECRET,
            "refresh_token": settings.BAZAAR_REFRESH_TOKEN,
        },
    )
    data = _json_body(raw)
    token = data.get("access_token")
    if not token:
        raise GatewayError(_redact(data.get("error_description") or data.get("error") or raw))
    _bazaar_token["access"] = token
    _bazaar_token["expires"] = now + int(data.get("expires_in") or 3600)
    return token


def bazaar_verify(sku, purchase_token):
    package_name = getattr(settings, "ANDROID_PACKAGE_NAME", "") or "ir.cafeclub.amytis"
    token = bazaar_access_token()
    url = (
        "https://pardakht.cafebazaar.ir/devapi/v2/api/validate/"
        f"{urllib.parse.quote(package_name)}/inapp/{urllib.parse.quote(sku)}"
        f"/purchases/{urllib.parse.quote(purchase_token)}/?access_token={urllib.parse.quote(token)}"
    )
    try:
        _status, raw = _request(url)
    except GatewayError:
        _bazaar_token["access"] = ""
        token = bazaar_access_token()
        url = (
            "https://pardakht.cafebazaar.ir/devapi/v2/api/validate/"
            f"{urllib.parse.quote(package_name)}/inapp/{urllib.parse.quote(sku)}"
            f"/purchases/{urllib.parse.quote(purchase_token)}/?access_token={urllib.parse.quote(token)}"
        )
        _status, raw = _request(url)
    data = _json_body(raw)
    if str(data.get("purchaseState")) != "0":
        raise GatewayError("خرید کافه بازار معتبر نیست.")
    return data


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
