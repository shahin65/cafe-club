import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from assistant.catalog import collect_payload, load_object
from assistant.clients import AssistantClientError, bale_configured, gapgpt_configured
from assistant.defaults import ensure_policies
from assistant.realtime import kick_realtime
from assistant.models import (
    ACTION_CHOICES,
    SCOPES,
    STATUS_NEEDS_REVIEW,
    STATUSES,
    AssistantConfig,
    AssistantRun,
    BaleReport,
    ReviewCase,
    ReviewPolicy,
)

HOUR_OPTIONS = list(range(24))


def _parse_hours(values):
    hours = []
    for raw in values:
        try:
            hour = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 <= hour <= 23 and hour not in hours:
            hours.append(hour)
    return hours


def _announce_realtime_kick(request):
    summary = kick_realtime()
    if summary.get("skipped") == "paused":
        messages.warning(request, "دستیار متوقف است؛ بلادرنگ اجرا نشد.")
        return
    if summary.get("skipped") == "off":
        return
    parts = [f"صف {summary.get('queued', 0)}", f"بررسی {summary.get('processed', 0)}"]
    if summary.get("errors"):
        parts.append(f"خطا {summary['errors']}")
    messages.info(request, "بلادرنگ صف را بررسی کرد: " + "، ".join(parts) + ". گزارش بله فقط بعد از اتمام هر مورد ارسال می‌شود.")


from assistant.reviewer import review_case

staff_page = staff_member_required(login_url="admin:login")


def _base_context():
    ensure_policies()
    return {
        "config": AssistantConfig.load(),
        "gapgpt_ok": gapgpt_configured(),
        "bale_ok": bale_configured(),
    }


@staff_page
def home(request):
    context = _base_context()
    sections = []
    policies = {item.scope: item for item in ReviewPolicy.objects.all()}
    for key, label in SCOPES:
        qs = ReviewCase.objects.filter(scope=key)
        policy = policies.get(key)
        sections.append(
            {
                "key": key,
                "label": label,
                "total": qs.count(),
                "pending": qs.filter(status="pending").count(),
                "review": qs.filter(status="needs_review").count(),
                "realtime_review": bool(policy and policy.realtime_review),
                "realtime_report": bool(policy and policy.realtime_report),
            }
        )
    context["sections"] = sections
    context["manager_count"] = ReviewCase.objects.filter(status=STATUS_NEEDS_REVIEW).count()
    return render(request, "admin/assistant/home.html", context)


@staff_page
def queue(request, scope):
    labels = dict(SCOPES)
    if scope not in labels:
        raise Http404()
    context = _base_context()
    status = request.GET.get("status") or ""
    cases = ReviewCase.objects.filter(scope=scope)
    if status:
        cases = cases.filter(status=status)
    page = Paginator(cases, 30).get_page(request.GET.get("page"))
    context.update(
        {
            "scope": scope,
            "title": labels[scope],
            "status": status,
            "status_choices": STATUSES,
            "cases": page.object_list,
            "page": page,
        }
    )
    return render(request, "admin/assistant/queue.html", context)


@staff_page
def manager_queue(request):
    context = _base_context()
    cases = ReviewCase.objects.filter(status=STATUS_NEEDS_REVIEW).select_related("manager_user")
    page = Paginator(cases, 30).get_page(request.GET.get("page"))
    context.update(
        {
            "title": "بازبینی مدیر",
            "cases": page.object_list,
            "page": page,
        }
    )
    return render(request, "admin/assistant/manager.html", context)


@staff_page
@require_http_methods(["GET", "POST"])
def case_detail(request, pk):
    case = get_object_or_404(ReviewCase, pk=pk)
    context = _base_context()
    obj = None
    obj_missing = False
    payload = {"fields": {}}
    try:
        obj = load_object(case)
        payload = collect_payload(case.source, obj)
    except Exception:
        obj_missing = True
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "dry":
                review_case(case, actor="ai", dry_run=True)
                messages.success(request, "اجرای آزمایشی انجام شد؛ نتیجه روی مورد اعمال نشد.")
            elif action == "run":
                review_case(case, actor="ai")
                messages.success(request, "بررسی دستی انجام شد.")
            elif action == "decide":
                send_reply = request.POST.get("send_reply") == "on"
                reply = (request.POST.get("reply") or "").strip()
                review_case(
                    case,
                    actor="manager",
                    user=request.user,
                    manager_decision=request.POST.get("status") or "needs_review",
                    manager_note=request.POST.get("note") or "",
                    manager_reply=reply if send_reply else "",
                )
                messages.success(request, "تصمیم مدیر ثبت شد.")
            next_name = request.POST.get("next") or request.GET.get("next")
            if next_name == "manager":
                return redirect("assistant_manager")
            return redirect("assistant_case", pk=case.pk)
        except AssistantClientError as exc:
            messages.error(request, str(exc))
        case.refresh_from_db()
    context.update(
        {
            "case": case,
            "obj_missing": obj_missing,
            "payload_pretty": json.dumps(payload.get("fields") or {}, ensure_ascii=False, indent=2),
            "status_choices": STATUSES,
            "events": case.events.select_related("actor_user")[:50],
            "next": request.GET.get("next") or request.POST.get("next") or "",
        }
    )
    return render(request, "admin/assistant/case.html", context)


@staff_page
@require_http_methods(["GET", "POST"])
def policy_edit(request, scope):
    labels = dict(SCOPES)
    if scope not in labels:
        raise Http404()
    ensure_policies()
    policy = get_object_or_404(ReviewPolicy, scope=scope)
    if request.method == "POST":
        policy.auto_enabled = request.POST.get("auto_enabled") == "on"
        policy.realtime_review = request.POST.get("realtime_review") == "on"
        policy.realtime_report = request.POST.get("realtime_report") == "on"
        policy.auto_reply_enabled = request.POST.get("auto_reply_enabled") == "on"
        policy.instructions = request.POST.get("instructions") or ""
        try:
            policy.confidence_threshold = Decimal(request.POST.get("confidence_threshold") or "0.85")
        except (InvalidOperation, ValueError):
            messages.error(request, "آستانه اطمینان نامعتبر است.")
            return redirect("assistant_policy", scope=scope)
        if policy.confidence_threshold < 0 or policy.confidence_threshold > 1:
            messages.error(request, "آستانه اطمینان باید بین ۰ و ۱ باشد.")
            return redirect("assistant_policy", scope=scope)
        policy.allowed_actions = [value for value in request.POST.getlist("allowed_actions") if value in dict(ACTION_CHOICES)]
        policy.updated_by = request.user
        policy.save()
        _announce_realtime_kick(request)
        messages.success(request, "معیارها ذخیره شد.")
        return redirect("assistant_policy", scope=scope)
    context = _base_context()
    context.update(
        {
            "scope": scope,
            "title": labels[scope],
            "policy": policy,
            "action_choices": ACTION_CHOICES,
        }
    )
    return render(request, "admin/assistant/policy.html", context)


@staff_page
@require_http_methods(["GET", "POST"])
def settings_page(request):
    config = AssistantConfig.load()
    if request.method == "POST":
        config.auto_paused = request.POST.get("auto_paused") == "on"
        config.review_hours = _parse_hours(request.POST.getlist("review_hours"))
        config.report_hours = _parse_hours(request.POST.getlist("report_hours"))
        config.report_purchases = request.POST.get("report_purchases") == "on"
        config.notes = request.POST.get("notes") or ""
        config.updated_by = request.user
        config.save()
        ensure_policies()
        for key, _label in SCOPES:
            policy = ReviewPolicy.objects.filter(scope=key).first()
            if not policy:
                continue
            policy.realtime_review = request.POST.get(f"realtime_review_{key}") == "on"
            policy.realtime_report = request.POST.get(f"realtime_report_{key}") == "on"
            policy.save(update_fields=["realtime_review", "realtime_report", "updated_at"])
        _announce_realtime_kick(request)
        messages.success(request, "تنظیمات ذخیره شد.")
        return redirect("assistant_settings")
    context = _base_context()
    context.update(
        {
            "hour_options": HOUR_OPTIONS,
            "review_hours": {int(hour) for hour in (config.review_hours or [])},
            "report_hours": {int(hour) for hour in (config.report_hours or [])},
            "policies": list(ReviewPolicy.objects.order_by("scope")),
        }
    )
    return render(request, "admin/assistant/settings.html", context)


@staff_page
def reports(request):
    context = _base_context()
    runs = list(AssistantRun.objects.all()[:30])
    reports_qs = list(BaleReport.objects.all()[:20])
    last_hourly = next((run for run in runs if run.kind == "hourly"), None)
    last_report_run = next((run for run in runs if run.kind == "report"), None)
    context.update(
        {
            "runs": runs,
            "reports": reports_qs,
            "last_hourly": last_hourly,
            "last_report_run": last_report_run,
        }
    )
    return render(request, "admin/assistant/reports.html", context)
