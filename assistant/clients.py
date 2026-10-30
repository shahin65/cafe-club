import json
import re
import ssl
import urllib.error
import urllib.request

from django.conf import settings


def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class AssistantClientError(Exception):
    pass


def _safe_error(exc):
    text = str(exc or "request failed")
    for secret in (settings.GAPGPT_API_KEY, settings.BALE_BOT_TOKEN):
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(r"bot[^/\s]+", "bot[redacted]", text)
    return text[:240]


def gapgpt_configured():
    return bool(settings.GAPGPT_API_KEY and settings.GAPGPT_BASE_URL and settings.GAPGPT_MODEL)


def bale_configured():
    return bool(settings.BALE_BOT_TOKEN and settings.BALE_ADMIN_CHAT_ID)


def complete_chat(messages, timeout=40):
    if not gapgpt_configured():
        raise AssistantClientError("سرویس هوش مصنوعی روی سرور پیکربندی نشده است.")
    endpoint = settings.GAPGPT_BASE_URL.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint}/chat/completions"
    payload = json.dumps(
        {
            "model": settings.GAPGPT_MODEL,
            "messages": messages,
            "temperature": 0.1,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.GAPGPT_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        except Exception:
            pass
        raise AssistantClientError(_safe_error(exc)) from None
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise AssistantClientError(_safe_error(exc)) from None
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AssistantClientError("پاسخ سرویس هوش مصنوعی قابل خواندن نبود.") from None


def send_bale_message(text, timeout=30):
    if not bale_configured():
        raise AssistantClientError("بات بله روی سرور پیکربندی نشده است.")
    url = f"https://tapi.bale.ai/bot{settings.BALE_BOT_TOKEN}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": settings.BALE_ADMIN_CHAT_ID,
            "text": text,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        except Exception:
            pass
        raise AssistantClientError(_safe_error(exc)) from None
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise AssistantClientError(_safe_error(exc)) from None
    if not body.get("ok"):
        raise AssistantClientError("ارسال گزارش به بله ناموفق بود.")
    return True
