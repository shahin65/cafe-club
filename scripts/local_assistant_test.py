"""One-shot local sample data + review + Bale report. Do not print secrets."""

import os
from datetime import timedelta
from io import BytesIO

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

django.setup()

from django.contrib.auth.models import User

from assistant.catalog import collect_payload
from assistant.clients import bale_configured, gapgpt_configured
from assistant.defaults import ensure_policies
from assistant.jobs import send_periodic_report
from assistant.models import (
    SOURCE_AD,
    SOURCE_SCENARIO_COMMENT,
    SOURCE_TICK,
    SCOPE_ADS,
    SCOPE_COMMENTS,
    SCOPE_TICKS,
    AssistantConfig,
    AssistantRun,
    BaleReport,
    ReviewCase,
)
from assistant.reviewer import review_case
from banners.models import BlueTickRequest, EventAd
from scenarios.models import Scenario, ScenarioComment


def _png():
    buffer = BytesIO()
    Image.new("RGB", (40, 40), (80, 50, 30)).save(buffer, format="PNG")
    return SimpleUploadedFile("assistant-test.png", buffer.getvalue(), content_type="image/png")


def main():
    ensure_policies()
    config = AssistantConfig.load()
    if config.auto_paused:
        config.auto_paused = False
        config.save(update_fields=["auto_paused"])
    AssistantRun.objects.filter(status="running").delete()
    BaleReport.objects.filter(sent_at__isnull=False).update(sent_at=None)

    user, created = User.objects.get_or_create(username="assistant_local_test")
    if created:
        user.set_password("unused-local-test")
        user.save()
    profile = user.club_profile
    profile.display_name = "میزبان تست دستیار"
    profile.save(update_fields=["display_name"])

    scenario = Scenario.objects.order_by("id").first()
    if scenario is None:
        scenario = Scenario.objects.create(name="سناریو تست دستیار")

    comment = ScenarioComment.objects.create(
        scenario=scenario,
        author_name="کاربر تست",
        body="شب خیلی خوبی بود، ممنون از برگزاری. امیدوارم بازم برگزار کنید.",
        is_approved=False,
        is_admin=False,
    )

    ad = EventAd(
        user=user,
        event_name="ایونت تست دستیار کافه کلاب",
        organizer_name="میزبان تست",
        address="خیابان ولیعصر، پلاک تست",
        starts_at="۲۲:۰۰",
        event_at=timezone.now() + timedelta(days=3),
        phone="09120000000",
        ticket_price="رایگان تست",
        cafe_bank="کافه تست",
        city="تهران",
        district="ونک",
        scenario="مافیا",
        expires_at=timezone.now() + timedelta(days=7),
        is_published=True,
        is_new=True,
    )
    ad.image = _png()
    ad.save()

    tick = BlueTickRequest.objects.create(
        user=user,
        full_name="میزبان تست دستیار",
        phone="09120000000",
        biography="گرداننده میز تست برای بررسی دستیار هوش مصنوعی. مدارک پیوست نشده است.",
        is_reviewed=False,
    )

    print("gapgpt", gapgpt_configured())
    print("bale", bale_configured())
    print("created", f"comment={comment.pk}", f"ad={ad.pk}", f"tick={tick.pk}")

    samples = [
        (SOURCE_SCENARIO_COMMENT, SCOPE_COMMENTS, comment),
        (SOURCE_AD, SCOPE_ADS, ad),
        (SOURCE_TICK, SCOPE_TICKS, tick),
    ]
    for source, scope, obj in samples:
        payload = collect_payload(source, obj)
        case, _ = ReviewCase.objects.get_or_create(
            source=source,
            object_id=obj.pk,
            defaults={
                "scope": scope,
                "submitted_at": payload["submitted_at"] or timezone.now(),
                "title": payload["title"][:200],
                "excerpt": payload["excerpt"],
            },
        )
        case.status = "pending"
        case.processing = False
        case.save(update_fields=["status", "processing"])
        try:
            review_case(case, actor="ai")
        except Exception as exc:
            print("review_error", source, type(exc).__name__, str(exc)[:200])
        case.refresh_from_db()
        print(
            "case",
            case.source,
            case.object_id,
            case.status,
            case.ai_decision,
            str(case.ai_confidence),
            (case.ai_reason or "")[:180],
            case.last_error[:80] if case.last_error else "",
        )

    report = send_periodic_report()
    print("report", report)


if __name__ == "__main__":
    main()
