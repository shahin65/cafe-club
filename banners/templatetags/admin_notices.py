from django import template
from django.urls import reverse

from banners.models import BlueTickRequest, EventAd, VenueComment, VenueSubmission
from scenarios.models import ScenarioComment

register = template.Library()


def _alarms():
    ads = EventAd.objects.filter(is_new=True).count()
    venues = VenueSubmission.objects.filter(is_reviewed=False).count()
    venue_comments = VenueComment.objects.filter(is_approved=False).count()
    scenario_comments = ScenarioComment.objects.filter(is_approved=False).count()
    ticks = BlueTickRequest.objects.filter(is_reviewed=False).count()
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
    ]


@register.inclusion_tag("admin/banners/new_ads_notice.html")
def new_ads_notice():
    alarms = [item for item in _alarms() if item["count"]]
    return {"alarms": alarms}


@register.inclusion_tag("admin/banners/admin_alarms.html")
def pending_admin_alarms():
    return {"alarms": [item for item in _alarms() if item["count"]]}
