from django import template
from django.urls import reverse

from banners.models import EventAd

register = template.Library()


@register.inclusion_tag("admin/banners/new_ads_notice.html")
def new_ads_notice():
    count = EventAd.objects.filter(is_new=True).count()
    return {
        "count": count,
        "url": reverse("admin:banners_eventad_changelist") + "?is_new__exact=1",
    }
