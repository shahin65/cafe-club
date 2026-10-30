from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from assistant.catalog import enqueue_new_items
from assistant.clients import AssistantClientError, _safe_error, send_bale_message
from assistant.models import (
    KIND_HOURLY,
    KIND_REPORT,
    RUN_DONE,
    RUN_ERROR,
    RUN_RUNNING,
    SCOPE_ADS,
    SCOPE_COMMENTS,
    SCOPE_TICKS,
    SCOPE_VENUES,
    STATUS_APPROVED,
    STATUS_NEEDS_REVIEW,
    STATUS_PENDING,
    STATUS_REJECTED,
    AssistantRun,
    BaleReport,
    ReviewCase,
)
from assistant.reviewer import process_pending


def _busy(kind, window_minutes):
    cutoff = timezone.now() - timedelta(minutes=window_minutes)
    return AssistantRun.objects.filter(kind=kind, status=RUN_RUNNING, started_at__gte=cutoff).exists()


def run_hourly():
    if _busy(KIND_HOURLY, 50):
        return {"skipped": "busy"}
    run = AssistantRun.objects.create(kind=KIND_HOURLY, status=RUN_RUNNING)
    try:
        queued = enqueue_new_items()
        result = process_pending()
        run.status = RUN_DONE
        run.finished_at = timezone.now()
        run.summary = {"queued": queued, **result}
        run.save(update_fields=["status", "finished_at", "summary"])
        return run.summary
    except Exception as exc:
        run.status = RUN_ERROR
        run.finished_at = timezone.now()
        run.error = _safe_error(exc)
        run.save(update_fields=["status", "finished_at", "error"])
        raise


def _count(qs):
    return qs.count()


def build_report(period_start, period_end):
    fresh = ReviewCase.objects.filter(submitted_at__gte=period_start, submitted_at__lt=period_end)
    backlog = ReviewCase.objects.filter(submitted_at__lt=period_start, status__in=[STATUS_PENDING, STATUS_NEEDS_REVIEW])

    def scoped(scope):
        items = fresh.filter(scope=scope)
        return {
            "received": _count(items),
            "approved": _count(items.filter(status=STATUS_APPROVED)),
            "rejected": _count(items.filter(status=STATUS_REJECTED)),
            "needs_review": _count(items.filter(status=STATUS_NEEDS_REVIEW)),
            "replied": _count(items.filter(reply_sent=True)) if scope == SCOPE_COMMENTS else 0,
        }

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "comments": scoped(SCOPE_COMMENTS),
        "ads": scoped(SCOPE_ADS),
        "venues": scoped(SCOPE_VENUES),
        "ticks": scoped(SCOPE_TICKS),
        "backlog": _count(backlog),
        "errors": AssistantRun.objects.filter(
            status=RUN_ERROR, started_at__gte=period_start, started_at__lt=period_end
        ).count()
        + ReviewCase.objects.filter(
            last_error__gt="", updated_at__gte=period_start, updated_at__lt=period_end
        ).count(),
    }


def format_report(data):
    comments = data["comments"]
    ads = data["ads"]
    venues = data["venues"]
    ticks = data["ticks"]
    return (
        "گزارش دستیار کافه کلاب\n"
        f"بازه: {data['period_start']} تا {data['period_end']}\n\n"
        f"نظرات: دریافتی {comments['received']}، تأیید {comments['approved']}، پاسخ {comments['replied']}، بازبینی {comments['needs_review']}، رد {comments['rejected']}\n"
        f"آگهی‌ها: دریافتی {ads['received']}، تأیید {ads['approved']}، بازبینی {ads['needs_review']}، رد {ads['rejected']}\n"
        f"کافه و کلاب: دریافتی {venues['received']}، تأیید {venues['approved']}، بازبینی {venues['needs_review']}، رد {venues['rejected']}\n"
        f"تیک آبی: دریافتی {ticks['received']}، تأیید {ticks['approved']}، بازبینی {ticks['needs_review']}، رد {ticks['rejected']}\n"
        f"معوق از بازه‌های قبل: {data['backlog']}\n"
        f"خطاهای پردازش: {data['errors']}"
    )


def send_periodic_report(hours=12, retry_failed=True):
    if _busy(KIND_REPORT, 10):
        return {"skipped": "busy"}
    end = timezone.now().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours)
    run = AssistantRun.objects.create(kind=KIND_REPORT, status=RUN_RUNNING)
    report, created = BaleReport.objects.get_or_create(period_start=start, period_end=end, defaults={"payload": {}})
    if report.sent_at:
        run.status = RUN_DONE
        run.finished_at = timezone.now()
        run.summary = {"skipped": "already_sent"}
        run.save(update_fields=["status", "finished_at", "summary"])
        return run.summary
    payload = build_report(start, end)
    report.payload = payload
    report.save(update_fields=["payload"])
    try:
        send_bale_message(format_report(payload))
        report.sent_at = timezone.now()
        report.last_error = ""
        report.save(update_fields=["sent_at", "last_error"])
        run.status = RUN_DONE
        run.finished_at = timezone.now()
        run.summary = {"sent": True, "created": created}
        run.save(update_fields=["status", "finished_at", "summary"])
        return run.summary
    except AssistantClientError as exc:
        report.retry_count += 1
        report.last_error = str(exc)[:240]
        report.save(update_fields=["retry_count", "last_error"])
        run.status = RUN_ERROR
        run.finished_at = timezone.now()
        run.error = report.last_error
        run.save(update_fields=["status", "finished_at", "error"])
        return {"sent": False, "error": report.last_error}


@transaction.atomic
def retry_failed_reports():
    results = []
    for report in BaleReport.objects.filter(sent_at__isnull=True).order_by("period_start")[:10]:
        try:
            send_bale_message(format_report(report.payload or build_report(report.period_start, report.period_end)))
            report.sent_at = timezone.now()
            report.last_error = ""
            report.save(update_fields=["sent_at", "last_error"])
            results.append(report.pk)
        except AssistantClientError as exc:
            report.retry_count += 1
            report.last_error = str(exc)[:240]
            report.save(update_fields=["retry_count", "last_error"])
    return results
