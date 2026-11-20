import os
from collections import Counter, defaultdict

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from django.utils.html import format_html, format_html_join

from .models import (
    KIND_SIDES,
    SIDE_CHOICES,
    SIDE_FIELDS,
    CardBranding,
    CatalogFinalCard,
    CatalogRole,
    FinalMoveCard,
    Role,
    Scenario,
    ScenarioComment,
    ScenarioSize,
)
from .widgets import ClearableAdminImageWidget, PageHtmlWidget

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


def _copy_image(src_file, dest, field_name):
    if not src_file:
        return
    src_file.open("rb")
    try:
        content = src_file.read()
    finally:
        src_file.close()
    getattr(dest, field_name).save(os.path.basename(src_file.name), ContentFile(content), save=True)


def _source_size_for(size, player_count=None):
    scenario_id = getattr(size, "scenario_id", None)
    if not scenario_id:
        return None
    count = player_count if player_count is not None else size.player_count
    qs = ScenarioSize.objects.filter(scenario_id=scenario_id)
    if size.pk:
        qs = qs.exclude(pk=size.pk)
    smaller = qs.filter(player_count__lt=count).order_by("-player_count").first()
    if smaller:
        return smaller
    return qs.order_by("player_count").first()


def _source_size_for_formset(formset):
    size = formset.instance
    parent = _parent_prefix(formset.prefix)
    raw_scenario = (formset.data or {}).get(f"{parent}-scenario" if parent else "scenario")
    if raw_scenario and not getattr(size, "scenario_id", None):
        try:
            size.scenario_id = int(raw_scenario)
        except (TypeError, ValueError):
            pass
    return _source_size_for(size, player_count=_posted_count(formset, "player_count"))


def inherit_size_content(size):
    source = _source_size_for(size)
    if not source:
        return
    dest_roles = defaultdict(list)
    for role in size.roles.order_by("id"):
        dest_roles[role.side].append(role)
    src_roles = defaultdict(list)
    for role in source.roles.order_by("id"):
        src_roles[role.side].append(role)
    for side, field in SIDE_FIELDS.items():
        needed = getattr(size, field) or 0
        dest = dest_roles.get(side, [])
        src = src_roles.get(side, [])
        dest_names = [role.name for role in dest]
        src_names = [role.name for role in src]
        extras_only = dest and src_names and not set(dest_names) & set(src_names)
        if extras_only:
            room = max(needed - len(dest), 0)
            for src_role in src[:room]:
                cloned = Role(
                    size=size,
                    side=side,
                    name=src_role.name,
                    description=src_role.description,
                )
                cloned.save()
                if src_role.icon:
                    _copy_image(src_role.icon, cloned, "icon")
            continue
        for index in range(needed):
            if index < len(dest):
                current = dest[index]
                if not current.icon and index < len(src) and src[index].icon:
                    _copy_image(src[index].icon, current, "icon")
                continue
            if index >= len(src):
                continue
            cloned = Role(
                size=size,
                side=side,
                name=src[index].name,
                description=src[index].description,
            )
            cloned.save()
            if src[index].icon:
                _copy_image(src[index].icon, cloned, "icon")
    dest_finals = list(size.final_move_cards.order_by("id"))
    src_finals = list(source.final_move_cards.order_by("id"))
    needed_finals = size.final_move_count or 0
    dest_final_names = [card.name for card in dest_finals]
    src_final_names = [card.name for card in src_finals]
    extras_only_finals = dest_finals and src_final_names and not set(dest_final_names) & set(src_final_names)
    if extras_only_finals:
        to_clone = src_finals[: max(needed_finals - len(dest_finals), 0)]
    else:
        to_clone = src_finals[len(dest_finals) : needed_finals]
    for src_card in to_clone:
        FinalMoveCard.objects.create(
            size=size,
            name=src_card.name,
            description=src_card.description,
            sort_order=src_card.sort_order,
        )


def _ordered_posted_names(formset, side):
    names = []
    for form in formset.forms:
        cleaned = getattr(form, "cleaned_data", None) or {}
        if cleaned.get("DELETE"):
            continue
        name = (cleaned.get("name") or "").strip()
        form_side = cleaned.get("side") or ""
        if not form_side and not name:
            continue
        if form_side == side:
            names.append(name)
    return names


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
        source = _source_size_for_formset(self)
        src_names = defaultdict(list)
        if source:
            for role in source.roles.order_by("id"):
                src_names[role.side].append(role.name)
        errors = []
        for side, field in SIDE_FIELDS.items():
            expected = _posted_count(self, field)
            posted_named = [name for name in _ordered_posted_names(self, side) if name]
            if len(posted_named) >= expected:
                continue
            combined = list(src_names.get(side, []))
            for name in posted_named:
                if name not in combined:
                    combined.append(name)
            if len(combined) < expected:
                errors.append(
                    f"برای ساید {SIDE_LABELS[side]} باید {expected} نقش وارد شود؛ "
                    f"نقش‌های قبلی کپی می‌شوند و فقط نقش‌های اضافه را بنویسید. الان {len(combined)} نقش آماده است."
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
        posted_named = [item["name"] for item in _filled_forms(self)]
        if len(posted_named) >= expected:
            return
        source = _source_size_for_formset(self)
        combined = [card.name for card in source.final_move_cards.order_by("id")] if source else []
        for name in posted_named:
            if name not in combined:
                combined.append(name)
        if len(combined) < expected:
            raise ValidationError(
                f"باید {expected} کارت حرکت آخر وارد شود؛ کارت‌های حالت قبلی کپی می‌شوند و فقط کارت‌های اضافه را بنویسید."
            )


class RoleEditForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ("side", "name", "description", "icon")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2, "cols": 40}),
            "icon": ClearableAdminImageWidget,
        }

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
        inherit_size_content(instance)

    def _save_named(self, formset, instance, queryset):
        formset.instance = instance
        kept = []
        for form in formset.forms:
            cleaned = getattr(form, "cleaned_data", None)
            if not cleaned or not cleaned.get("name"):
                continue
            form.instance.size = instance
            saved = form.save()
            if "icon" in getattr(form, "fields", {}):
                clear_key = f"{form.add_prefix('icon')}-clear"
                posted = form.data if form.data is not None else formset.data
                uploaded = form.files.get(form.add_prefix("icon")) if form.files else None
                should_clear = cleaned.get("icon") is False or (posted and posted.get(clear_key) and not uploaded)
                if should_clear:
                    if saved.icon:
                        saved.icon.delete(save=False)
                    saved.icon = ""
                    saved.save(update_fields=["icon"])
            kept.append(saved)
        queryset.exclude(pk__in=[item.pk for item in kept]).delete()


class ScenarioSizeInline(admin.StackedInline):
    model = ScenarioSize
    form = ScenarioSizeForm
    formset = ScenarioSizeFormSet
    extra = 1
    max_num = 5
    classes = ["collapse"]
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
    verbose_name_plural = "حالت‌های اجرا (حداکثر ۵؛ نقش‌های قبلی خودکار کپی می‌شوند)"


class RoleInline(admin.TabularInline):
    model = Role
    form = RoleEditForm
    formset = RoleFormSet
    extra = 0
    fields = ("side", "name", "description", "icon")

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:
            return 0
        return max(obj.side_total() - obj.roles.count(), 0)


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


def _catalog_role_inline_for(side):
    label = SIDE_LABELS[side]

    class CatalogSideRoleFormSet(BaseInlineFormSet):
        @classmethod
        def get_default_prefix(cls):
            return f"catalog_{side}_roles"

        def save_new(self, form, commit=True):
            form.instance.side = side
            return super().save_new(form, commit=commit)

        def save_existing(self, form, instance, commit=True):
            form.instance.side = side
            return super().save_existing(form, instance, commit=commit)

    class CatalogSideRoleInline(admin.TabularInline):
        model = CatalogRole
        extra = 2
        fields = ("name", "allows_quantity", "description", "sort_order")
        formset = CatalogSideRoleFormSet
        verbose_name = f"نقش {label}"
        verbose_name_plural = f"نقش‌های ساید {label} (هر تعداد اضافه کنید)"

        def get_queryset(self, request):
            return super().get_queryset(request).filter(side=side)

    CatalogSideRoleFormSet.__name__ = f"Catalog{side.capitalize()}RoleFormSet"
    CatalogSideRoleInline.__name__ = f"Catalog{side.capitalize()}RoleInline"
    return CatalogSideRoleInline


CATALOG_ROLE_INLINES = {side: _catalog_role_inline_for(side) for side, _label in SIDE_CHOICES}


class CatalogFinalInline(admin.TabularInline):
    model = CatalogFinalCard
    extra = 3
    fields = ("name", "description", "sort_order")


class ScenarioCatalogFilter(admin.SimpleListFilter):
    title = "گروه سناریو"
    parameter_name = "catalog"

    def lookups(self, request, model_admin):
        return (
            ("quick", "تقسیم نقش سریع"),
            ("large", "سناریوهای تعداد بالا"),
            ("custom", "سناریوهای دلخواه من"),
        )

    def queryset(self, request, queryset):
        custom = Q(owner__isnull=False) | ~Q(guest_key="")
        if self.value() == "quick":
            return queryset.filter(is_large=False).exclude(custom)
        if self.value() == "large":
            return queryset.filter(is_large=True).exclude(custom)
        if self.value() == "custom":
            return queryset.filter(custom)
        return queryset


class ScenarioAdmin(admin.ModelAdmin):
    change_list_template = "admin/scenarios/scenario/change_list.html"
    list_display = ("name", "catalog_group", "slug", "is_large", "large_kind", "owner", "player_modes", "has_final_move", "has_death_lottery", "is_featured", "home_order")
    list_filter = (ScenarioCatalogFilter, "is_large", "large_kind", "is_featured", "has_final_move", "has_death_lottery", "owner")
    search_fields = ("name", "slug")
    ordering = ("home_order", "-id")
    inlines = (ScenarioSizeInline,)
    fieldsets = (
        ("سناریو", {"fields": ("name", "slug", "owner", "guest_key", "icon", "is_large", "large_kind", "has_final_move", "has_death_lottery")}),
        (
            "صفحه اول",
            {
                "fields": ("is_featured", "home_order"),
                "description": "تعداد ردیف اسم و توضیح نقش برابر تعداد نفرات همان حالت است. کارت‌های حرکت آخر هم به همان تعداد وارد می‌شوند.",
            },
        ),
        (
            "رول‌بوک‌ها",
            {
                "classes": ("collapse",),
                "fields": ("rulebook_title_fa", "rulebook_body_fa"),
            },
        ),
        (
            "قوانین",
            {
                "classes": ("collapse",),
                "fields": ("rules_title_fa", "rules_body_fa"),
            },
        ),
    )

    class Media:
        js = ("admin/js/scenario-size-slots.js",)
        css = {"all": ("admin/css/scenario-size-slots.css",)}

    def get_inlines(self, request, obj=None):
        if obj and obj.is_large:
            sides = KIND_SIDES.get(obj.large_kind) or [side for side, _label in SIDE_CHOICES]
            items = [CATALOG_ROLE_INLINES[side] for side in sides]
            if obj.large_kind == "night" or obj.has_final_move:
                items.append(CatalogFinalInline)
            return items
        return (ScenarioSizeInline,)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "icon":
            kwargs["widget"] = ClearableAdminImageWidget
        if db_field.name in {"rulebook_body_fa", "rules_body_fa"}:
            kwargs["widget"] = PageHtmlWidget(language="fa")
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        upload = form.cleaned_data.get("icon") if form and hasattr(form, "cleaned_data") else None
        if isinstance(upload, UploadedFile):
            from banners.images import optimize_image

            obj.icon = optimize_image(upload, max_edge=720)
        super().save_model(request, obj, form, change)

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

    @admin.display(description="گروه")
    def catalog_group(self, obj):
        if obj.is_custom():
            return "سناریوهای دلخواه من"
        if obj.is_large:
            return "سناریوهای تعداد بالا"
        return "تقسیم نقش سریع"

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        context = getattr(response, "context_data", None)
        if not context or "cl" not in context:
            return response
        qs = context["cl"].queryset
        custom = Q(owner__isnull=False) | ~Q(guest_key="")
        groups = (
            ("تقسیم نقش سریع", qs.filter(is_large=False).exclude(custom)),
            ("سناریوهای تعداد بالا", qs.filter(is_large=True).exclude(custom)),
            ("سناریوهای دلخواه من", qs.filter(custom)),
        )
        context["scenario_groups"] = [
            {
                "title": title,
                "items": list(items.select_related("owner").prefetch_related("sizes").order_by("home_order", "-id")[:300]),
                "count": items.count(),
            }
            for title, items in groups
        ]
        return response

    @admin.display(description="حالت‌های نفرات")
    def player_modes(self, obj):
        counts = [str(size.player_count) for size in obj.sizes.all()]
        return "، ".join(counts) if counts else "—"


admin.site.register(Scenario, ScenarioAdmin)
admin.site.register(ScenarioSize, ScenarioSizeAdmin)
admin.site.register(ScenarioComment, ScenarioCommentAdmin)
admin.site.register(CardBranding)
