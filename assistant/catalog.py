from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

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
    ReviewCase,
)


def _clip(text, size=400):
    value = " ".join(str(text or "").split())
    return value[:size]


def collect_payload(source, obj):
    if source == SOURCE_SCENARIO_COMMENT:
        return {
            "title": f"نظر سناریو {obj.scenario_id}",
            "excerpt": _clip(f"{obj.author_name}: {obj.body}"),
            "submitted_at": obj.created_at,
            "fields": {
                "author": obj.author_name,
                "scenario": str(obj.scenario_id),
                "body": obj.body,
            },
        }
    if source == SOURCE_VENUE_COMMENT:
        return {
            "title": f"نظر کافه {obj.venue_id}",
            "excerpt": _clip(f"{obj.author_name}: {obj.body}"),
            "submitted_at": obj.created_at,
            "fields": {"author": obj.author_name, "venue": str(obj.venue_id), "body": obj.body},
        }
    if source == SOURCE_AD:
        return {
            "title": obj.event_name,
            "excerpt": _clip(f"{obj.event_name} / {obj.city} / {obj.scenario}"),
            "submitted_at": obj.created_at,
            "fields": {
                "event_name": obj.event_name,
                "organizer_name": obj.organizer_name,
                "address": obj.address,
                "phone": obj.phone,
                "city": obj.city,
                "district": obj.district,
                "scenario": obj.scenario,
                "ticket_price": obj.ticket_price,
                "cafe_bank": obj.cafe_bank,
            },
        }
    if source == SOURCE_VENUE:
        return {
            "title": obj.name,
            "excerpt": _clip(f"{obj.name} / {obj.city} / {obj.address}"),
            "submitted_at": obj.created_at,
            "fields": {
                "name": obj.name,
                "manager_name": obj.manager_name,
                "address": obj.address,
                "phone": obj.phone,
                "hours": obj.hours,
                "city": obj.city,
            },
        }
    return {
        "title": obj.full_name,
        "excerpt": _clip(f"{obj.full_name} / {obj.phone}"),
        "submitted_at": obj.created_at,
        "fields": {
            "full_name": obj.full_name,
            "phone": obj.phone,
            "biography": obj.biography,
            "username": obj.user.get_username(),
        },
    }


def load_object(case):
    model = {
        SOURCE_SCENARIO_COMMENT: ("scenarios", "scenariocomment"),
        SOURCE_VENUE_COMMENT: ("banners", "venuecomment"),
        SOURCE_AD: ("banners", "eventad"),
        SOURCE_VENUE: ("banners", "venuesubmission"),
        SOURCE_TICK: ("banners", "bluetickrequest"),
    }[case.source]
    ct = ContentType.objects.get(app_label=model[0], model=model[1])
    return ct.get_object_for_this_type(pk=case.object_id)


def enqueue_object(source, scope, obj):
    payload = collect_payload(source, obj)
    case, created = ReviewCase.objects.get_or_create(
        source=source,
        object_id=obj.pk,
        defaults={
            "scope": scope,
            "submitted_at": payload["submitted_at"] or timezone.now(),
            "title": payload["title"][:200],
            "excerpt": payload["excerpt"],
        },
    )
    return case, created


def enqueue_new_items():
    from banners.models import BlueTickRequest, EventAd, VenueComment, VenueSubmission
    from scenarios.models import ScenarioComment

    created = 0
    batches = [
        (SOURCE_SCENARIO_COMMENT, SCOPE_COMMENTS, ScenarioComment.objects.filter(is_admin=False, is_approved=False)),
        (SOURCE_VENUE_COMMENT, SCOPE_COMMENTS, VenueComment.objects.filter(is_approved=False)),
        (SOURCE_AD, SCOPE_ADS, EventAd.objects.filter(is_new=True)),
        (SOURCE_VENUE, SCOPE_VENUES, VenueSubmission.objects.filter(is_reviewed=False)),
        (SOURCE_TICK, SCOPE_TICKS, BlueTickRequest.objects.filter(is_reviewed=False)),
    ]
    for source, scope, queryset in batches:
        existing = set(ReviewCase.objects.filter(source=source).values_list("object_id", flat=True))
        for obj in queryset.iterator():
            if obj.pk in existing:
                continue
            _case, was_created = enqueue_object(source, scope, obj)
            if was_created:
                created += 1
            existing.add(obj.pk)
    return created


def apply_to_object(case, decision, reply=""):
    obj = load_object(case)
    if case.source in {SOURCE_SCENARIO_COMMENT, SOURCE_VENUE_COMMENT}:
        if decision == "approve":
            if not obj.is_approved:
                obj.is_approved = True
                obj.save(update_fields=["is_approved"])
            if reply and case.source == SOURCE_SCENARIO_COMMENT:
                from scenarios.models import ScenarioComment

                if not obj.replies.filter(is_admin=True).exists():
                    ScenarioComment.objects.create(
                        scenario=obj.scenario,
                        parent=obj,
                        author_name="مدیریت",
                        body=reply[:1000],
                        is_approved=True,
                        is_admin=True,
                    )
                    case.reply_sent = True
            return "approve"
        if decision == "reject":
            if obj.is_approved:
                obj.is_approved = False
                obj.save(update_fields=["is_approved"])
            return "reject"
        return "needs_review"
    if case.source == SOURCE_AD:
        if decision == "approve":
            obj.is_published = True
            obj.is_new = False
            obj.save(update_fields=["is_published", "is_new"])
            return "approve"
        if decision == "reject":
            obj.is_published = False
            obj.is_new = False
            obj.save(update_fields=["is_published", "is_new"])
            return "reject"
        if obj.is_new:
            obj.is_new = False
            obj.save(update_fields=["is_new"])
        return "needs_review"
    if case.source == SOURCE_VENUE:
        from banners.venues import publish_venue_submission

        if decision == "approve":
            publish_venue_submission(obj)
            return "approve"
        if decision == "reject":
            if not obj.is_reviewed:
                obj.is_reviewed = True
                obj.save(update_fields=["is_reviewed"])
            return "reject"
        return "needs_review"
    if decision == "approve":
        obj.mark_approved()
        return "approve"
    if decision == "reject":
        obj.mark_rejected()
        return "reject"
    return "needs_review"
