from collections import Counter

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html

from .models import SIDE_FIELDS, FinalMoveCard, Role, Scenario, ScenarioSize

SIDE_LABELS = dict(Role._meta.get_field("side").choices)


def _filled_forms(formset):
    forms = []
    for form in formset.forms:
        cleaned = getattr(form, "cleaned_data", None)
        if not cleaned or cleaned.get("DELETE"):
            continue
        if not cleaned.get("name"):
            continue
        forms.append(cleaned)
    return forms


class ScenarioSizeFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return
        has_final_move = "has_final_move" in self.data
        total = 0
        seen = set()
        errors = []
        for form in self.forms:
            cleaned = getattr(form, "cleaned_data", None)
            if not cleaned or cleaned.get("DELETE"):
                continue
            player_count = cleaned.get("player_count")
            if not player_count:
                continue
            total += 1
            if player_count in seen:
                errors.append(f"حالت {player_count} نفره تکرار شده است.")
            seen.add(player_count)
            side_total = sum(cleaned.get(field, 0) or 0 for field in SIDE_FIELDS.values())
            if side_total != player_count:
                errors.append(
                    f"در حالت {player_count} نفره، جمع مافیا، شهروند، مستقل و گرگینه باید دقیقاً {player_count} باشد؛ الان {side_total} است."
                )
            if has_final_move and not cleaned.get("final_move_count"):
                errors.append(f"برای حالت {player_count} نفره تعداد کارت حرکت آخر را مشخص کنید.")
        if total > 5:
            errors.append("هر سناریو حداکثر ۵ حالت تعداد نفرات می‌تواند داشته باشد.")
        if errors:
            raise ValidationError(errors)


class ScenarioSizeInline(admin.StackedInline):
    model = ScenarioSize
    formset = ScenarioSizeFormSet
    extra = 1
    max_num = 5
    show_change_link = True
    fields = (
        "player_count",
        "mafia_count",
        "citizen_count",
        "independent_count",
        "werewolf_count",
        "final_move_count",
    )
    verbose_name = "حالت تعداد نفرات"
    verbose_name_plural = "حالت‌های اجرا (حداکثر ۵)"


class RoleFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return
        actual = Counter()
        for cleaned in _filled_forms(self):
            actual[cleaned["side"]] += 1
        errors = []
        for side, field in SIDE_FIELDS.items():
            expected = int(self.data.get(field) or 0)
            if actual[side] != expected:
                errors.append(
                    f"برای ساید {SIDE_LABELS[side]} باید {expected} نقش وارد شود؛ الان {actual[side]} نقش ثبت شده است."
                )
        if errors:
            raise ValidationError(errors)


class FinalMoveFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return
        expected = int(self.data.get("final_move_count") or 0)
        actual = len(_filled_forms(self))
        if actual != expected:
            raise ValidationError(
                f"باید {expected} کارت حرکت آخر وارد شود؛ الان {actual} کارت ثبت شده است."
            )


class RoleInline(admin.TabularInline):
    model = Role
    formset = RoleFormSet
    extra = 0
    fields = ("side", "name", "description", "icon", "icon_preview")
    readonly_fields = ("icon_preview",)

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:
            return 0
        return max(obj.side_total() - obj.roles.count(), 0)

    @admin.display(description="پیش‌نمایش آیکون")
    def icon_preview(self, obj):
        if getattr(obj, "icon", None) and getattr(obj.icon, "name", ""):
            return format_html('<img src="{}" alt="" class="banner-preview">', obj.icon.url)
        return "—"


class FinalMoveCardInline(admin.TabularInline):
    model = FinalMoveCard
    formset = FinalMoveFormSet
    extra = 0
    fields = ("sort_order", "name", "description")

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None or not obj.final_move_count:
            return 0
        return max(obj.final_move_count - obj.final_move_cards.count(), 0)


class ScenarioSizeAdmin(admin.ModelAdmin):
    list_display = ("scenario", "player_count", "mafia_count", "citizen_count", "independent_count", "werewolf_count")
    inlines = (RoleInline, FinalMoveCardInline)
    fields = (
        "scenario",
        "player_count",
        "mafia_count",
        "citizen_count",
        "independent_count",
        "werewolf_count",
        "final_move_count",
    )

    def has_module_permission(self, request):
        return False

    def get_inline_instances(self, request, obj=None):
        inlines = [RoleInline]
        if obj and obj.scenario.has_final_move:
            inlines.append(FinalMoveCardInline)
        return [inline(self.model, self.admin_site) for inline in inlines]


class ScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "player_modes", "has_final_move", "has_death_lottery", "is_featured", "home_order")
    list_filter = ("is_featured", "has_final_move", "has_death_lottery")
    search_fields = ("name",)
    ordering = ("home_order", "id")
    inlines = (ScenarioSizeInline,)
    readonly_fields = ("icon_preview",)
    fieldsets = (
        ("سناریو", {"fields": ("name", "icon", "icon_preview", "has_final_move", "has_death_lottery")}),
        (
            "صفحه اول",
            {
                "fields": ("is_featured", "home_order"),
                "description": "بعد از ذخیره، برای هر حالت روی «تغییر» بزنید و نقش‌ها را کامل کنید. سپس تا ۶ سناریوی کامل را تأیید کنید. ترتیب صفحه اول هر عددی می‌تواند باشد و سقف آن سه نیست.",
            },
        ),
    )

    @admin.display(description="آیکون")
    def icon_preview(self, obj):
        if getattr(obj, "icon", None) and getattr(obj.icon, "name", ""):
            return format_html('<img src="{}" alt="" class="banner-preview">', obj.icon.url)
        return "—"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        scenario = Scenario.objects.get(pk=form.instance.pk)
        if not scenario.is_featured:
            return
        already = Scenario.objects.filter(is_featured=True).exclude(pk=scenario.pk).count()
        if already >= 6 or not scenario.is_complete():
            scenario.is_featured = False
            scenario.save(update_fields=["is_featured"])
            if already >= 6:
                messages.error(
                    request,
                    "سقف صفحه اول ۶ سناریو است. تأیید این سناریو ذخیره نشد.",
                )
            else:
                messages.error(
                    request,
                    "تأیید صفحه اول ذخیره نشد چون نقش‌ها هنوز کامل نیستند. این محدودیت سه سناریو نیست؛ هر سناریوی کامل تا سقف ۶ تا قابل تأیید است.",
                )

    @admin.display(description="حالت‌های نفرات")
    def player_modes(self, obj):
        counts = [str(size.player_count) for size in obj.sizes.all()]
        return "، ".join(counts) if counts else "—"


admin.site.register(Scenario, ScenarioAdmin)
admin.site.register(ScenarioSize, ScenarioSizeAdmin)
