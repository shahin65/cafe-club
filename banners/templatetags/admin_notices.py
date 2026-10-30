from django import template
from django.urls import reverse

from assistant.models import (
    SOURCE_AD,
    SOURCE_SCENARIO_COMMENT,
    SOURCE_TICK,
    SOURCE_VENUE,
    SOURCE_VENUE_COMMENT,
    STATUS_NEEDS_REVIEW,
    STATUS_PENDING,
    ReviewCase,
)
from banners.models import BlueTickRequest, EventAd, VenueComment, VenueSubmission
from scenarios.models import ScenarioComment

register = template.Library()


def _unhandled(source, queryset):
    handled = ReviewCase.objects.filter(source=source).exclude(status=STATUS_PENDING).values_list("object_id", flat=True)
    return queryset.exclude(pk__in=handled).count()


def _alarms():
    ads = _unhandled(SOURCE_AD, EventAd.objects.filter(is_new=True))
    venues = _unhandled(SOURCE_VENUE, VenueSubmission.objects.filter(is_reviewed=False))
    venue_comments = _unhandled(SOURCE_VENUE_COMMENT, VenueComment.objects.filter(is_approved=False))
    scenario_comments = _unhandled(SOURCE_SCENARIO_COMMENT, ScenarioComment.objects.filter(is_approved=False, is_admin=False))
    ticks = _unhandled(SOURCE_TICK, BlueTickRequest.objects.filter(is_reviewed=False))
    return [
        {
            "key": "ads",
            "label": "آگهی جدید",
            "count": ads,
            "url": reverse("admin:banners_eventad_changelist") + "?is_new__exact=1",
        },
        {
            "key": "venues",
            "label": "ثبت کافه یا کلاب",
            "count": venues,
            "url": reverse("admin:banners_venuesubmission_changelist") + "?is_reviewed__exact=0",
        },
        {
            "key": "messages",
            "label": "پیام جدید",
            "count": scenario_comments,
            "url": reverse("admin:scenarios_scenariocomment_changelist") + "?is_approved__exact=0",
        },
        {
            "key": "comments",
            "label": "نظرات کافه",
            "count": venue_comments,
            "url": reverse("admin:banners_venuecomment_changelist") + "?is_approved__exact=0",
        },
        {
            "key": "ticks",
            "label": "تیک آبی",
            "count": ticks,
            "url": reverse("admin:banners_bluetickrequest_changelist") + "?is_reviewed__exact=0",
        },
        {
            "key": "manager",
            "label": "بازبینی مدیر",
            "count": ReviewCase.objects.filter(status=STATUS_NEEDS_REVIEW).count(),
            "url": reverse("assistant_manager"),
        },
    ]


@register.inclusion_tag("admin/banners/new_ads_notice.html")
def new_ads_notice():
    alarms = [item for item in _alarms() if item["count"]]
    return {"alarms": alarms}


@register.inclusion_tag("admin/banners/admin_alarms.html")
def pending_admin_alarms():
    return {"alarms": [item for item in _alarms() if item["count"]]}
