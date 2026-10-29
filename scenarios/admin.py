from collections import Counter

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from django.utils.html import format_html, format_html_join

from .models import SIDE_FIELDS, CardBranding, FinalMoveCard, Role, Scenario, ScenarioComment, ScenarioSize
from .widgets import PageHtmlWidget

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


def _parent_prefix(prefix):
    prefix = prefix or ""
    if prefix in {"roles", "finals"}:
        return ""
    for suffix in ("-roles", "-finals"):
        if prefix.endswith(suffix):
            return prefix[: -len(suffix)]
    return ""


def _posted_count(formset, field):
    parent = _parent_prefix(formset.prefix)
    key = f"{parent}-{field}" if parent else field
    raw = (formset.data or {}).get(key)
    if raw not in (None, ""):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    return int(getattr(formset.instance, field, 0) or 0)


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

    def save_new(self, form, commit=True):
        instance = super().save_new(form, commit=commit)
        form.save_nested(instance)
        return instance

    def save_existing(self, form, instance, commit=True):
        instance = super().save_existing(form, instance, commit=commit)
        form.save_nested(instance)
        return instance


class RoleFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return
        if not _posted_count(self, "player_count"):
            return
        actual = Counter()
        for cleaned in _filled_forms(self):
            actual[cleaned["side"]] += 1
        errors = []
        for side, field in SIDE_FIELDS.items():
            expected = _posted_count(self, field)
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
        if "has_final_move" not in (self.data or {}) and not getattr(getattr(self.instance, "scenario", None), "has_final_move", False):
            return
        if not _posted_count(self, "player_count"):
            return
        expected = _posted_count(self, "final_move_count")
        actual = len(_filled_forms(self))
        if actual != expected:
            raise ValidationError(
                f"باید {expected} کارت حرکت آخر وارد شود؛ الان {actual} کارت ثبت شده است."
            )


class RoleEditForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ("side", "name", "description", "icon")
        widgets = {"description": forms.Textarea(attrs={"rows": 2, "cols": 40})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["side"].required = False
        self.fields["name"].required = False
        self.fields["description"].required = False


class FinalMoveEditForm(forms.ModelForm):
    class Meta:
        model = FinalMoveCard
        fields = ("name", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 2, "cols": 40})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = False
        self.fields["description"].required = False


ROLE_SLOT_COUNT = 20
FINAL_SLOT_COUNT = 12


def _nested_role_formset(instance, data, files, prefix):
    existing = instance.roles.count() if instance and instance.pk else 0
    factory = inlineformset_factory(
        ScenarioSize,
        Role,
        form=RoleEditForm,
        formset=RoleFormSet,
        extra=max(ROLE_SLOT_COUNT - existing, 0),
        max_num=ROLE_SLOT_COUNT,
        can_delete=False,
    )
    return factory(data=data, files=files, instance=instance, prefix=prefix)


def _nested_final_formset(instance, data, files, prefix):
    existing = instance.final_move_cards.count() if instance and instance.pk else 0
    factory = inlineformset_factory(
        ScenarioSize,
        FinalMoveCard,
        form=FinalMoveEditForm,
        formset=FinalMoveFormSet,
        extra=max(FINAL_SLOT_COUNT - existing, 0),
        max_num=FINAL_SLOT_COUNT,
        can_delete=False,
    )
    return factory(data=data, files=files, instance=instance, prefix=prefix)


class ScenarioSizeForm(forms.ModelForm):
    class Meta:
        model = ScenarioSize
        fields = (
            "player_count",
            "mafia_count",
            "citizen_count",
            "independent_count",
            "werewolf_count",
            "final_move_count",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        prefix = self.prefix
        data = self.data if self.is_bound else None
        files = self.files if self.is_bound else None
        instance = self.instance if self.instance.pk else ScenarioSize()
        self.nested_roles = _nested_role_formset(instance, data, files, f"{prefix}-roles")
        self.nested_finals = _nested_final_formset(instance, data, files, f"{prefix}-finals")

    def is_valid(self):
        valid = super().is_valid()
        if self.cleaned_data.get("DELETE") or not self.cleaned_data.get("player_count"):
            return valid
        return valid and self.nested_roles.is_valid() and self.nested_finals.is_valid()

    def save_nested(self, instance):
        if self.cleaned_data.get("DELETE"):
            return
        self._save_named(self.nested_roles, instance, instance.roles)
        self._save_named(self.nested_finals, instance, instance.final_move_cards)

    def _save_named(self, formset, instance, queryset):
        formset.instance = instance
        kept = []
        for form in formset.forms:
            cleaned = getattr(form, "cleaned_data", None)
            if not cleaned or not cleaned.get("name"):
                continue
            form.instance.size = instance
            kept.append(form.save())
        queryset.exclude(pk__in=[item.pk for item in kept]).delete()


class ScenarioSizeInline(admin.StackedInline):
    model = ScenarioSize
    form = ScenarioSizeForm
    formset = ScenarioSizeFormSet
    extra = 1
    max_num = 5
    show_change_link = False
    template = "admin/scenarios/size_stacked.html"
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
    fields = ("name", "description")

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


class ScenarioCommentAdminForm(forms.ModelForm):
    admin_reply = forms.CharField(
        label="متن پاسخ مدیریت",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "cols": 80}),
        help_text="با ذخیره، این متن به‌عنوان پاسخ تأییدشدهٔ مدیریت زیر همین نظر ثبت می‌شود.",
    )

    class Meta:
        model = ScenarioComment
        fields = ("scenario", "parent", "author_name", "body", "is_approved", "is_admin")


class ScenarioCommentAdmin(admin.ModelAdmin):
    form = ScenarioCommentAdminForm
    list_display = ("short_body", "scenario", "author_name", "is_approved", "is_admin", "has_admin_reply", "created_at")
    list_filter = ("is_approved", "is_admin", "scenario")
    search_fields = ("author_name", "body", "scenario__name")
    list_select_related = ("scenario", "parent")
    ordering = ("-created_at",)
    actions = ("approve_comments",)
    readonly_fields = ("created_at", "existing_replies")

    def get_fieldsets(self, request, obj=None):
        main = (
            "نظر کاربر",
            {"fields": ("scenario", "author_name", "body", "is_approved", "created_at")},
        )
        if obj and not obj.is_admin:
            return (
                main,
                (
                    "پاسخ مدیریت",
                    {
                        "fields": ("existing_replies", "admin_reply"),
                        "description": "پاسخ را بنویسید و ذخیره کنید. نظر کاربر هم در صورت نیاز تأیید می‌شود.",
                    },
                ),
            )
        return (main,)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("replies")

    @admin.display(description="متن")
    def short_body(self, obj):
        return obj.body[:60]

    @admin.display(description="پاسخ مدیریت", boolean=True)
    def has_admin_reply(self, obj):
        if obj.is_admin:
            return False
        return any(reply.is_admin for reply in obj.replies.all())

    @admin.display(description="پاسخ‌های ثبت‌شده")
    def existing_replies(self, obj):
        if not getattr(obj, "pk", None):
            return "—"
        items = [reply.body for reply in obj.replies.all() if reply.is_admin]
        if not items:
            return "هنوز پاسخ مدیریت ثبت نشده است."
        return format_html("<ul class='admin-comment-replies'>{}</ul>", format_html_join("", "<li>{}</li>", ((item,) for item in items)))

    @admin.action(description="تأیید نظرهای انتخاب‌شده")
    def approve_comments(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} نظر تأیید شد.")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        reply = (form.cleaned_data.get("admin_reply") or "").strip()
        if not reply or obj.is_admin:
            return
        if not obj.is_approved:
            obj.is_approved = True
            obj.save(update_fields=["is_approved"])
        ScenarioComment.objects.create(
            scenario=obj.scenario,
            parent=obj,
            author_name="مدیریت",
            body=reply,
            is_approved=True,
            is_admin=True,
        )
        self.message_user(request, "پاسخ مدیریت ثبت شد و زیر نظر کاربر نمایش داده می‌شود.")


class ScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "player_modes", "has_final_move", "has_death_lottery", "is_featured", "home_order")
    list_filter = ("is_featured", "has_final_move", "has_death_lottery", "owner")
    search_fields = ("name", "name_en", "slug")
    ordering = ("home_order", "id")
    inlines = (ScenarioSizeInline,)
    readonly_fields = ("icon_preview",)
    fieldsets = (
        ("سناریو", {"fields": ("name", "name_en", "slug", "owner", "guest_key", "icon", "icon_preview", "has_final_move", "has_death_lottery")}),
        (
            "صفحه اول",
            {
                "fields": ("is_featured", "home_order"),
                "description": "تعداد ردیف اسم و توضیح نقش برابر تعداد نفرات همان حالت است. کارت‌های حرکت آخر هم به همان تعداد وارد می‌شوند.",
            },
        ),
        ("رول‌بوک فارسی", {"fields": ("rulebook_title_fa", "rulebook_body_fa")}),
        ("رول‌بوک انگلیسی", {"fields": ("rulebook_title_en", "rulebook_body_en")}),
        ("قوانین فارسی", {"fields": ("rules_title_fa", "rules_body_fa")}),
        ("قوانین انگلیسی", {"fields": ("rules_title_en", "rules_body_en")}),
    )

    class Media:
        js = ("admin/js/scenario-size-slots.js",)
        css = {"all": ("admin/css/scenario-size-slots.css",)}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in {"rulebook_body_fa", "rules_body_fa"}:
            kwargs["widget"] = PageHtmlWidget(language="fa")
        elif db_field.name in {"rulebook_body_en", "rules_body_en"}:
            kwargs["widget"] = PageHtmlWidget(language="en")
        return super().formfield_for_dbfield(db_field, request, **kwargs)

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
admin.site.register(ScenarioComment, ScenarioCommentAdmin)
admin.site.register(CardBranding)
