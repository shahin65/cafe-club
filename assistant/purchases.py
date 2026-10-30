from assistant.clients import AssistantClientError, bale_configured, send_bale_message
from assistant.models import AssistantConfig


def report_completed_purchase(txn):
    config = AssistantConfig.load()
    if not config.report_purchases or not bale_configured():
        return False
    payload = dict(txn.payload or {})
    if payload.get("bale_reported"):
        return False
    user = txn.user
    package = txn.package
    lines = [
        "گزارش خرید جدید",
        f"خریدار: {user.get_username() if user else '—'}",
        f"ایمیل: {(user.email if user else '') or '—'}",
        f"محصول: {package.title if package else '—'} ({package.sku if package else '—'})",
        f"مبلغ: {txn.amount_toman} تومان",
        f"درگاه: {txn.get_gateway_display()}",
        f"منبع ورود: {txn.source or '—'}",
        f"توکن خرید: {txn.purchase_token or '—'}",
    ]
    if txn.bitpay_trans_id:
        lines.append(f"تراکنش بیت‌پی: {txn.bitpay_trans_id}")
    if txn.event_ad_id:
        lines.append(f"آگهی: {txn.event_ad.event_name}")
    if txn.venue_id:
        lines.append(f"کافه / کلاب: {txn.venue.name}")
    try:
        send_bale_message("\n".join(lines))
    except AssistantClientError as exc:
        payload["bale_error"] = str(exc)[:240]
        txn.payload = payload
        txn.save(update_fields=["payload"])
        return False
    payload["bale_reported"] = True
    payload.pop("bale_error", None)
    txn.payload = payload
    txn.save(update_fields=["payload"])
    return True
