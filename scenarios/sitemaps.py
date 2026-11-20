from django.contrib.sitemaps import Sitemap

from scenarios.models import Scenario


class ScenarioRulebookSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    i18n = False
    alternates = False
    x_default = False

    def items(self):
        return [item for item in Scenario.objects.filter(owner__isnull=True).exclude(slug="") if item.has_indexable_page("rulebook")]

    def location(self, obj):
        return obj.get_rulebook_url()


class ScenarioRulesSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    i18n = False
    alternates = False
    x_default = False

    def items(self):
        return [item for item in Scenario.objects.filter(owner__isnull=True).exclude(slug="") if item.has_indexable_page("rules")]

    def location(self, obj):
        return obj.get_rules_url()


SITEMAPS = {
    "scenario-rulebook": ScenarioRulebookSitemap,
    "scenario-rules": ScenarioRulesSitemap,
}
