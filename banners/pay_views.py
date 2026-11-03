from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from banners.app_source import normalize_source
from banners.catalog import fulfill_purchase
from banners.gateways import (
    GatewayError,
    bazaar_configured,
    bazaar_verify,
    bitpay_configured,
    bitpay_request,
    bitpay_verify,
    gateway_for_source,
    myket_configured,
    myket_verify,
)
from banners.models import CoinPackage, PaymentTransaction
from banners.promo import PLANS, VENUE_PLANS


def install_source(request):
    return normalize_source(getattr(request, "app_source", "")) or "direct"


def success_url(txn):
    package = txn.package
    if package.kind == CoinPackage.KIND_AD and txn.event_ad_id:
        ad = txn.event_ad
        plan = PLANS.get(package.plan_key) or {}
        if plan.get("needs_extras") and not ad.has_nav():
            return reverse("ad_promo_extras", args=[ad.id])
        if (txn.payload or {}).get("return") == "ads":
            return reverse("ads")
        return reverse("ad_detail", args=[ad.id])
    if package.kind == CoinPackage.KIND_VENUE and txn.venue_id:
        plan = VENUE_PLANS.get(package.plan_key) or {}
        if plan.get("show_on_home"):
            return reverse("home")
        return reverse("location")
    if package.kind == CoinPackage.KIND_LAB:
        return reverse("dev_lab")
    return reverse("ads")


def success_message(txn):
    package = txn.package
    if package.kind == CoinPackage.KIND_AD:
        plan = PLANS.get(package.plan_key) or {}
        name = txn.event_ad.event_name if txn.event_ad_id else package.title
        return f"پلن {plan.get('title', package.title)} برای «{name}» فعال شد."
    if package.kind == CoinPackage.KIND_VENUE:
        plan = VENUE_PLANS.get(package.plan_key) or {}
        name = txn.venue.name if txn.venue_id else package.title
        return f"پلن {plan.get('title', package.title)} برای «{name}» فعال شد."
    if package.kind == CoinPackage.KIND_LAB:
        return f"خرید آزمایشی «{package.title}» ثبت شد."
    return "پرداخت با موفقیت انجام شد."


def _complete(txn, *, purchase_token="", trans_id="", payload=None):
    try:
        with transaction.atomic():
            locked = (
                PaymentTransaction.objects.select_for_update()
                .select_related("package", "event_ad", "venue")
                .get(pk=txn.pk)
            )
            if locked.status == PaymentTransaction.STATUS_COMPLETED:
                return locked
            token = (purchase_token or "").strip()
            if token:
                duplicate = (
                    PaymentTransaction.objects.select_for_update()
                    .filter(gateway=locked.gateway, purchase_token=token)
                    .exclude(pk=locked.pk)
                    .first()
                )
                if duplicate:
                    raise GatewayError("این خرید قبلاً ثبت شده است.")
                locked.purchase_token = token
            locked.status = PaymentTransaction.STATUS_COMPLETED
            locked.completed_at = timezone.now()
            locked.bitpay_trans_id = (trans_id or locked.bitpay_trans_id)[:40]
            merged = dict(locked.payload or {})
            if payload:
                merged["gateway"] = payload
            locked.payload = merged
            locked.save(
                update_fields=["purchase_token", "status", "completed_at", "bitpay_trans_id", "payload"]
            )
            fulfill_purchase(locked)
    except IntegrityError as exc:
        raise GatewayError("این خرید قبلاً ثبت شده است.") from exc
    from assistant.purchases import report_completed_purchase

    try:
        report_completed_purchase(locked)
    except Exception:
        pass
    return locked


def start_checkout(request, package, *, event_ad=None, venue=None, fail_url="ads", return_to="", gateway=""):
    source = install_source(request)
    gateway = gateway or gateway_for_source(source)
    txn = PaymentTransaction.objects.create(
        user=request.user,
        package=package,
        event_ad=event_ad,
        venue=venue,
        gateway=gateway,
        source=source,
        amount_toman=package.price_toman,
        status=PaymentTransaction.STATUS_PENDING,
        payload={"return": return_to} if return_to else {},
    )
    bypass = (
        settings.DEBUG
        and package.kind != CoinPackage.KIND_LAB
        and (
            (gateway == PaymentTransaction.GATEWAY_BITPAY and not bitpay_configured())
            or (gateway == PaymentTransaction.GATEWAY_BAZAAR and not bazaar_configured())
            or (gateway == PaymentTransaction.GATEWAY_MYKET and not myket_configured())
        )
    )
    if bypass:
        _complete(txn)
        txn.refresh_from_db()
        messages.success(request, success_message(txn))
        return redirect(success_url(txn))
    if gateway == PaymentTransaction.GATEWAY_BITPAY:
        try:
            callback = request.build_absolute_uri(reverse("bitpay_callback"))
            id_get, redirect_url = bitpay_request(
                package.price_toman,
                txn.id,
                callback,
                name=request.user.get_username(),
                email=request.user.email or "",
                description=package.title,
            )
        except GatewayError as exc:
            txn.status = PaymentTransaction.STATUS_FAILED
            txn.payload = {"error": str(exc)}
            txn.save(update_fields=["status", "payload"])
            messages.error(request, str(exc))
            return redirect(fail_url)
        txn.bitpay_id_get = id_get
        txn.save(update_fields=["bitpay_id_get"])
        return redirect(redirect_url)
    request.session["pending_payment_id"] = txn.id
    request.session.modified = True
    return redirect("pay_checkout", txn_id=txn.id)


def _finish_response(request, txn, *, wants_json=False, replay=False):
    next_url = success_url(txn)
    if wants_json:
        return JsonResponse(
            {
                "ok": True,
                "status": "completed",
                "sku": txn.package.sku,
                "replay": replay,
                "next": next_url,
            }
        )
    if replay:
        messages.info(request, "این خرید قبلاً اعمال شده است.")
    else:
        messages.success(request, success_message(txn))
    return redirect(next_url)


@login_required
@require_GET
def checkout_page(request, txn_id):
    txn = get_object_or_404(
        PaymentTransaction.objects.select_related("package", "event_ad", "venue"),
        pk=txn_id,
        user=request.user,
    )
    if txn.status == PaymentTransaction.STATUS_COMPLETED:
        messages.success(request, success_message(txn))
        return redirect(success_url(txn))
    source = install_source(request)
    gateway = txn.gateway or gateway_for_source(source)
    verify_name = "verify_bazaar" if gateway == PaymentTransaction.GATEWAY_BAZAAR else "verify_myket"
    return render(
        request,
        "account/checkout.html",
        {
            "txn": txn,
            "package": txn.package,
            "install_source": source,
            "gateway": gateway,
            "verify_url": reverse(verify_name),
        },
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def bitpay_callback(request):
    trans_id = (request.POST.get("trans_id") or request.GET.get("trans_id") or "").strip()
    id_get = (request.POST.get("id_get") or request.GET.get("id_get") or "").strip()
    if not trans_id or not id_get:
        messages.error(request, "بازگشت از درگاه بیت‌پی ناقص بود.")
        return redirect("ads")
    txn = (
        PaymentTransaction.objects.select_related("package", "event_ad", "venue")
        .filter(gateway=PaymentTransaction.GATEWAY_BITPAY, bitpay_id_get=id_get)
        .first()
    )
    if not txn:
        messages.error(request, "تراکنش بیت‌پی پیدا نشد.")
        return redirect("ads")
    try:
        payload = bitpay_verify(trans_id, id_get)
        paid = int(payload.get("amount") or 0)
        expected = txn.amount_toman * 10
        if paid and paid != expected:
            raise GatewayError("مبلغ پرداخت با بسته هم‌خوانی ندارد.")
        _complete(txn, trans_id=trans_id, payload=payload)
        txn.refresh_from_db()
    except GatewayError as exc:
        if txn.status != PaymentTransaction.STATUS_COMPLETED:
            txn.status = PaymentTransaction.STATUS_FAILED
            txn.payload = {"error": str(exc)}
            txn.save(update_fields=["status", "payload"])
        messages.error(request, str(exc))
        return redirect("ads")
    messages.success(request, success_message(txn))
    return redirect(success_url(txn))


def _verify_store(request, gateway):
    sku = (request.POST.get("sku") or "").strip()
    purchase_token = (request.POST.get("purchase_token") or "").strip()
    wants_json = "application/json" in (request.headers.get("Accept") or "") or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    fail_url = "ads"
    if not sku or not purchase_token:
        error = "شناسه محصول و توکن خرید را بفرستید."
        if wants_json:
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect(fail_url)
    package = CoinPackage.objects.filter(sku=sku, is_active=True).first()
    if not package:
        error = "محصول پیدا نشد."
        if wants_json:
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect(fail_url)
    try:
        if gateway == PaymentTransaction.GATEWAY_BAZAAR:
            payload = bazaar_verify(
                sku,
                purchase_token,
                original_json=request.POST.get("original_json") or "",
                signature=request.POST.get("signature") or "",
            )
        else:
            payload = myket_verify(sku, purchase_token)
        existing = PaymentTransaction.objects.select_related("package", "event_ad", "venue").filter(
            gateway=gateway, purchase_token=purchase_token
        ).first()
        if existing:
            if existing.status == PaymentTransaction.STATUS_COMPLETED:
                return _finish_response(request, existing, wants_json=wants_json, replay=True)
            txn = existing
        else:
            pending_id = request.session.get("pending_payment_id")
            txn = (
                PaymentTransaction.objects.select_related("package", "event_ad", "venue")
                .filter(
                    pk=pending_id,
                    user=request.user,
                    package=package,
                    gateway=gateway,
                    status=PaymentTransaction.STATUS_PENDING,
                )
                .first()
            )
            if not txn:
                txn = PaymentTransaction.objects.create(
                    user=request.user,
                    package=package,
                    gateway=gateway,
                    source=install_source(request),
                    amount_toman=package.price_toman,
                    status=PaymentTransaction.STATUS_PENDING,
                )
        _complete(txn, purchase_token=purchase_token, payload=payload)
        txn.refresh_from_db()
    except GatewayError as exc:
        if wants_json:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, str(exc))
        pending_id = request.session.get("pending_payment_id")
        if pending_id:
            return redirect("pay_checkout", txn_id=pending_id)
        return redirect(fail_url)
    return _finish_response(request, txn, wants_json=wants_json)


@login_required
@require_POST
def verify_bazaar(request):
    return _verify_store(request, PaymentTransaction.GATEWAY_BAZAAR)


@login_required
@require_POST
def verify_myket(request):
    return _verify_store(request, PaymentTransaction.GATEWAY_MYKET)
