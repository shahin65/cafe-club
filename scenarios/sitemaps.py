from django.contrib.sitemaps import Sitemap

from scenarios.models import Scenario


class ScenarioRulebookSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    i18n = True
    alternates = True
    x_default = True

    def items(self):
        return [item for item in Scenario.objects.exclude(slug="") if item.has_indexable_page("rulebook")]

    def location(self, obj):
        return obj.get_rulebook_url()


class ScenarioRulesSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    i18n = True
    alternates = True
    x_default = True

    def items(self):
        return [item for item in Scenario.objects.exclude(slug="") if item.has_indexable_page("rules")]

    def location(self, obj):
        return obj.get_rules_url()


SITEMAPS = {
    "scenario-rulebook": ScenarioRulebookSitemap,
    "scenario-rules": ScenarioRulesSitemap,
}
