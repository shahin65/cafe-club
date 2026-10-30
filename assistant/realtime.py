from django.db import transaction

from assistant.catalog import enqueue_new_items, enqueue_object
from assistant.clients import AssistantClientError, send_bale_message
from assistant.models import (
    SCOPE_ADS,
    SCOPE_COMMENTS,
    SCOPE_TICKS,
    SCOPE_VENUES,
    SOURCE_AD,
    SOURCE_SCENARIO_COMMENT,
    SOURCE_TICK,
    SOURCE_VENUE,
    SOURCE_VENUE_COMMENT,
    AssistantConfig,
    ReviewPolicy,
)
from assistant.reviewer import process_pending


def _alert(case):
    status = case.get_status_display()
    reason = (case.ai_reason or case.last_error or "").strip()
    text = (
        f"گزارش لحظه‌ای دستیار\n"
        f"بخش: {case.get_scope_display()}\n"
        f"{case.title}\n"
        f"وضعیت: {status}"
    )
    if reason:
        text += f"\n{reason[:400]}"
    send_bale_message(text)


def report_finished_case(case):
    _alert(case)


def handle_new_item(source, scope, obj):
    config = AssistantConfig.load()
    policy = ReviewPolicy.objects.filter(scope=scope).first()
    if config.auto_paused or not policy:
        return
    if not policy.realtime_review and not policy.realtime_report:
        return
    enqueue_object(source, scope, obj)
    process_pending(limit=8, scope=scope)


def schedule_new_item(source, scope, obj):
    pk = obj.pk
    model = obj.__class__

    def _run():
        fresh = model.objects.filter(pk=pk).first()
        if not fresh:
            return
        handle_new_item(source, scope, fresh)

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_run)
    else:
        _run()


def kick_realtime():
    config = AssistantConfig.load()
    policies = list(ReviewPolicy.objects.all())
    if config.auto_paused:
        return {"skipped": "paused", "queued": 0, "processed": 0, "errors": 0, "sent": False, "error": ""}
    if not any(policy.realtime_review or policy.realtime_report for policy in policies):
        return {"skipped": "off", "queued": 0, "processed": 0, "errors": 0, "sent": False, "error": ""}
    queued = enqueue_new_items()
    processed = 0
    errors = 0
    for policy in policies:
        if policy.realtime_review or policy.realtime_report:
            result = process_pending(limit=50, scope=policy.scope)
            processed += result.get("processed", 0)
            errors += result.get("errors", 0)
    return {
        "queued": queued,
        "processed": processed,
        "errors": errors,
        "sent": False,
        "error": "",
    }


_signals_connected = False


def connect_signals():
    global _signals_connected
    if _signals_connected:
        return
    _signals_connected = True
    from django.db.models.signals import post_save

    from banners.models import BlueTickRequest, EventAd, VenueComment, VenueSubmission
    from scenarios.models import ScenarioComment

    def on_scenario_comment(sender, instance, created, **kwargs):
        if created and not instance.is_admin:
            schedule_new_item(SOURCE_SCENARIO_COMMENT, SCOPE_COMMENTS, instance)

    def on_venue_comment(sender, instance, created, **kwargs):
        if created:
            schedule_new_item(SOURCE_VENUE_COMMENT, SCOPE_COMMENTS, instance)

    def on_ad(sender, instance, created, **kwargs):
        if created:
            schedule_new_item(SOURCE_AD, SCOPE_ADS, instance)

    def on_venue(sender, instance, created, **kwargs):
        if created:
            schedule_new_item(SOURCE_VENUE, SCOPE_VENUES, instance)

    def on_tick(sender, instance, created, **kwargs):
        if created:
            schedule_new_item(SOURCE_TICK, SCOPE_TICKS, instance)

    post_save.connect(on_scenario_comment, sender=ScenarioComment, weak=False)
    post_save.connect(on_venue_comment, sender=VenueComment, weak=False)
    post_save.connect(on_ad, sender=EventAd, weak=False)
    post_save.connect(on_venue, sender=VenueSubmission, weak=False)
    post_save.connect(on_tick, sender=BlueTickRequest, weak=False)
