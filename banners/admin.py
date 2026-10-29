from django import forms
from django.contrib import admin, messages
from django.core.files.uploadedfile import UploadedFile
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from banners.geo import IRAN_CITIES
from banners.images import optimize_image, optimize_venue_image
from banners.models import Banner, BlueTickRequest, EventAd, LegalPage, SiteLink, SiteSettings, UserProfile, Venue, VenueComment, VenueRating, VenueSubmission


class BannerAdmin(admin.ModelAdmin):
    list_display = (
        "image_preview",
        "title_fa",
        "title_en",
        "display_order",
        "is_active",
    )
    list_display_links = ("title_fa",)
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title_fa", "title_en", "description_fa", "description_en")
    search_help_text = "جستجو در عنوان و توضیحات فارسی و انگلیسی"
    ordering = ("display_order", "pk")
    empty_value_display = "—"
    readonly_fields = ("image_preview_large",)
    actions = ("activate_banners", "deactivate_banners")
    fieldsets = (
        (
            "محتوای فارسی",
            {"fields": ("title_fa", "description_fa")},
        ),
        (
            "محتوای انگلیسی",
            {
                "fields": ("title_en", "description_en"),
                "description": "این متن‌ها فقط وقتی دیده می‌شوند که زبان سایت انگلیسی باشد.",
            },
        ),
        (
            "تصویر",
            {"fields": ("image", "image_preview_large")},
        ),
        (
            "پیوندها",
            {"fields": ("internal_url", "external_url")},
        ),
        (
            "نمایش",
            {"fields": ("is_active", "display_order")},
        ),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        ltr_fields = {
            "title_en": None,
            "description_en": None,
            "external_url": "https://",
            "internal_url": "/nights/",
        }
        for name, placeholder in ltr_fields.items():
            field = form.base_fields.get(name)
            if field is None:
                continue
            field.widget.attrs["dir"] = "ltr"
            if placeholder:
                field.widget.attrs["placeholder"] = placeholder
        description = form.base_fields.get("description_fa")
        if description is not None:
            description.widget.attrs["rows"] = 4
        description_en = form.base_fields.get("description_en")
        if description_en is not None:
            description_en.widget.attrs["rows"] = 4
        return form

    @admin.display(description="پیش‌نمایش")
    def image_preview(self, obj):
        if getattr(obj, "image", None) and getattr(obj.image, "name", ""):
            return format_html(
                '<img src="{}" alt="" class="banner-preview">',
                obj.image.url,
            )
        return "—"

    @admin.display(description="پیش‌نمایش تصویر")
    def image_preview_large(self, obj):
        if getattr(obj, "image", None) and getattr(obj.image, "name", ""):
            return format_html(
                '<img src="{}" alt="" class="banner-preview-large">',
                obj.image.url,
            )
        return "پس از ذخیره، پیش‌نمایش تصویر اینجا دیده می‌شود."

    @admin.action(description="فعال‌سازی بنرهای انتخاب‌شده")
    def activate_banners(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} بنر فعال شد.")

    @admin.action(description="غیرفعال‌سازی بنرهای انتخاب‌شده")
    def deactivate_banners(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} بنر غیرفعال شد.")


admin.site.register(Banner, BannerAdmin)


class UserProfileAdmin(admin.ModelAdmin):
    change_list_template = "admin/banners/userprofile/change_list.html"
    list_display = ("public_id_display", "user", "google_email", "app_source", "is_verified")
    list_filter = ("is_verified", "app_source")
    search_fields = ("public_id", "user__username", "display_name", "google_email")
    search_help_text = "جستجو با شناسه شش‌رقمی، نام کاربری یا جیمیل"
    readonly_fields = ("public_id", "user", "google_email", "google_sub")
    fields = ("user", "public_id", "display_name", "is_verified", "app_source", "google_email", "bio", "photo")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "activate/",
                self.admin_site.admin_view(self.activate_blue_tick),
                name="banners_userprofile_activate",
            )
        ]
        return custom + urls

    def activate_blue_tick(self, request):
        if request.method != "POST":
            return redirect("admin:banners_userprofile_changelist")
        raw = (request.POST.get("public_id") or "").strip()
        action = request.POST.get("action")
        if not raw.isdigit() or len(raw) != 6:
            self.message_user(request, "شناسه باید دقیقاً شش رقم باشد.", level=messages.ERROR)
            return redirect("admin:banners_userprofile_changelist")
        profile = UserProfile.objects.filter(public_id=int(raw)).select_related("user").first()
        if not profile:
            self.message_user(request, "کاربری با این شناسه پیدا نشد.", level=messages.ERROR)
            return redirect("admin:banners_userprofile_changelist")
        if action == "deactivate":
            profile.is_verified = False
            profile.save(update_fields=["is_verified"])
            self.message_user(request, f"تیک آبی {profile.public_id_display()} خاموش شد.")
        else:
            profile.is_verified = True
            profile.save(update_fields=["is_verified"])
            self.message_user(request, f"تیک آبی {profile.public_id_display()} برای {profile.user.get_username()} فعال شد.")
        return redirect("admin:banners_userprofile_changelist")


admin.site.register(UserProfile, UserProfileAdmin)


class BlueTickRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "phone", "created_at", "is_reviewed")
    list_filter = ("is_reviewed",)
    search_fields = ("full_name", "phone", "user__username", "biography")
    list_editable = ("is_reviewed",)


admin.site.register(BlueTickRequest, BlueTickRequestAdmin)


class EventAdAdmin(admin.ModelAdmin):
    list_display = (
        "image_preview",
        "event_name",
        "organizer_name",
        "user",
        "starts_at",
        "phone",
        "is_published",
        "is_new",
        "created_at",
        "expires_at",
    )
    list_display_links = ("event_name",)
    list_filter = ("is_published", "is_new")
    list_editable = ("is_published",)
    search_fields = ("event_name", "organizer_name", "phone", "address", "cafe_bank", "city", "district", "scenario", "user__username")
    readonly_fields = ("user", "created_at", "expires_at", "image_preview_large")
    actions = ("unpublish_ads", "publish_ads")
    ordering = ("-created_at",)
    fieldsets = (
        (
            "آگهی",
            {
                "fields": (
                    "event_name",
                    "organizer_name",
                    "image",
                    "image_preview_large",
                    "address",
                    "starts_at",
                    "phone",
                    "ticket_price",
                    "cafe_bank",
                    "city",
                    "district",
                    "scenario",
                )
            },
        ),
        ("نمایش", {"fields": ("is_published", "is_new", "user", "created_at", "expires_at")}),
    )

    @admin.display(description="تصویر")
    def image_preview(self, obj):
        if getattr(obj, "image", None) and getattr(obj.image, "name", ""):
            return format_html('<img src="{}" alt="" class="banner-preview">', obj.image.url)
        return "—"

    @admin.display(description="پیش‌نمایش تصویر")
    def image_preview_large(self, obj):
        if getattr(obj, "image", None) and getattr(obj.image, "name", ""):
            return format_html('<img src="{}" alt="" class="banner-preview-large">', obj.image.url)
        return "—"

    @admin.action(description="خروج از انتشار / لغو آگهی‌های انتخاب‌شده")
    def unpublish_ads(self, request, queryset):
        updated = queryset.update(is_published=False, is_new=False)
        self.message_user(request, f"{updated} آگهی از حالت انتشار خارج شد.")

    @admin.action(description="انتشار آگهی‌های انتخاب‌شده")
    def publish_ads(self, request, queryset):
        updated = queryset.update(is_published=True, is_new=False)
        self.message_user(request, f"{updated} آگهی منتشر شد.")

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if object_id:
            EventAd.objects.filter(pk=object_id, is_new=True).update(is_new=False)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if change:
            obj.is_new = False
        super().save_model(request, obj, form, change)


admin.site.register(EventAd, EventAdAdmin)


class VenueAdminForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        city = self.fields.get("city")
        if city is not None:
            city.widget.attrs["list"] = "iran-cities"
            city.widget.attrs["placeholder"] = "تهران"
        for name in ("latitude", "longitude", "phone"):
            field = self.fields.get(name)
            if field is not None:
                field.widget.attrs["dir"] = "ltr"
        hours = self.fields.get("hours")
        if hours is not None:
            hours.widget.attrs["placeholder"] = "شنبه تا چهارشنبه ۱۶ تا ۲۴"


class VenueAdmin(admin.ModelAdmin):
    form = VenueAdminForm
    change_form_template = "admin/banners/venue/change_form.html"
    list_display = ("logo_preview", "name", "city", "manager_name", "phone", "is_active", "has_map_point")
    list_display_links = ("name",)
    list_filter = ("city", "is_active")
    search_fields = ("name", "city", "manager_name", "address", "phone")
    list_editable = ("is_active",)
    ordering = ("city", "name")
    fieldsets = (
        ("مشخصات", {"fields": ("name", "city", "logo", "manager_name", "is_active")}),
        ("تصاویر", {"fields": ("photo_1", "photo_2", "photo_3")}),
        ("ارتباط و ساعت", {"fields": ("hours", "address", "phone")}),
        (
            "موقعیت روی نقشه",
            {
                "fields": ("latitude", "longitude"),
                "description": "روی نقشه کلیک کنید یا بکشید تا موقعیت کافه ثبت شود.",
            },
        ),
    )

    class Media:
        css = {
            "all": [
                "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
                "admin/css/venue-map.css",
            ]
        }
        js = [
            "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
            "admin/js/venue-map.js",
        ]

    @admin.display(description="لوگو")
    def logo_preview(self, obj):
        if getattr(obj, "logo", None) and getattr(obj.logo, "name", ""):
            return format_html('<img src="{}" alt="" class="banner-preview">', obj.logo.url)
        return "—"

    @admin.display(description="نقشه", boolean=True)
    def has_map_point(self, obj):
        return obj.has_point()

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["iran_cities"] = IRAN_CITIES
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        image_fields = {"logo": 512, "photo_1": 1200, "photo_2": 1200, "photo_3": 1200}
        for name, edge in image_fields.items():
            upload = form.cleaned_data.get(name)
            if isinstance(upload, UploadedFile):
                setattr(obj, name, optimize_venue_image(upload, max_edge=edge))
        super().save_model(request, obj, form, change)


class VenueCommentAdmin(admin.ModelAdmin):
    list_display = ("short_body", "venue", "author_name", "is_approved", "created_at")
    list_filter = ("is_approved", "venue")
    search_fields = ("author_name", "body", "venue__name")
    list_editable = ("is_approved",)
    actions = ("approve_comments", "reject_comments")
    ordering = ("-created_at",)

    @admin.display(description="متن")
    def short_body(self, obj):
        return obj.body[:60]

    @admin.action(description="تأیید نظرهای انتخاب‌شده")
    def approve_comments(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} نظر تأیید شد.")

    @admin.action(description="رد نظرهای انتخاب‌شده")
    def reject_comments(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f"{updated} نظر از حالت تأیید خارج شد.")


class VenueRatingAdmin(admin.ModelAdmin):
    list_display = ("venue", "stars", "user", "created_at")
    list_filter = ("stars", "venue")
    search_fields = ("venue__name", "user__username")
    readonly_fields = ("venue", "user", "guest_key", "stars", "created_at", "updated_at")


class VenueSubmissionAdmin(admin.ModelAdmin):
    list_display = ("name", "manager_name", "phone", "city", "is_reviewed", "created_at")
    list_filter = ("is_reviewed",)
    search_fields = ("name", "manager_name", "phone", "address")
    list_editable = ("is_reviewed", "city")
    actions = ("publish_to_list",)
    readonly_fields = ("user", "created_at")
    fieldsets = (
        ("درخواست", {"fields": ("name", "logo", "manager_name", "address", "phone", "hours", "city", "latitude", "longitude")}),
        ("تصاویر", {"fields": ("photo_1", "photo_2", "photo_3")}),
        ("بررسی", {"fields": ("user", "is_reviewed", "created_at")}),
    )

    @admin.action(description="ثبت انتخاب‌شده‌ها در لیست کافه‌ها و کلاب‌ها")
    def publish_to_list(self, request, queryset):
        created = 0
        skipped = 0
        for item in queryset:
            if not (item.city or "").strip():
                skipped += 1
                continue
            venue = Venue(
                name=item.name,
                city=item.city.strip(),
                manager_name=item.manager_name,
                address=item.address,
                phone=item.phone,
                hours=item.hours,
                latitude=item.latitude,
                longitude=item.longitude,
                is_active=True,
            )
            if item.logo:
                venue.logo = item.logo
            if item.photo_1:
                venue.photo_1 = item.photo_1
            if item.photo_2:
                venue.photo_2 = item.photo_2
            if item.photo_3:
                venue.photo_3 = item.photo_3
            venue.save()
            item.is_reviewed = True
            item.save(update_fields=["is_reviewed"])
            created += 1
        if created:
            self.message_user(request, f"{created} کافه در لیست ثبت شد.")
        if skipped:
            self.message_user(request, f"{skipped} مورد بدون شهر رد شد. ابتدا شهر را وارد کنید.", level=messages.ERROR)


class SiteLinkAdmin(admin.ModelAdmin):
    list_display = ("icon_preview", "title", "group", "key", "url", "is_active", "sort_order")
    list_filter = ("group", "is_active")
    list_editable = ("is_active", "sort_order")
    search_fields = ("title", "title_en", "url")
    ordering = ("group", "sort_order", "id")
    fieldsets = (
        ("مورد", {"fields": ("group", "key", "title", "title_en")}),
        ("لینک و تصویر", {"fields": ("url", "image"), "description": "لینک دانلود یا شبکه اجتماعی و آیکون مربوط به همان مورد."}),
        ("نمایش", {"fields": ("is_active", "sort_order")}),
    )

    @admin.display(description="آیکون")
    def icon_preview(self, obj):
        if getattr(obj, "image", None) and getattr(obj.image, "name", ""):
            return format_html('<img src="{}" alt="" class="banner-preview">', obj.image.url)
        return "—"

    def save_model(self, request, obj, form, change):
        upload = form.cleaned_data.get("image")
        if isinstance(upload, UploadedFile):
            obj.image = optimize_image(upload, max_edge=512)
        super().save_model(request, obj, form, change)


class LegalPageAdmin(admin.ModelAdmin):
    list_display = ("title", "key")
    search_fields = ("title", "title_en", "body", "body_en")
    fields = ("key", "title", "title_en", "body", "body_en")
    readonly_fields = ("key",)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        for name in ("body", "body_en"):
            field = form.base_fields.get(name)
            if field is not None:
                field.widget.attrs["rows"] = 18
        return form

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Venue, VenueAdmin)
admin.site.register(VenueComment, VenueCommentAdmin)
admin.site.register(VenueRating, VenueRatingAdmin)
admin.site.register(VenueSubmission, VenueSubmissionAdmin)
admin.site.register(SiteLink, SiteLinkAdmin)
admin.site.register(LegalPage, LegalPageAdmin)


@require_POST
def toggle_maintenance(request):
    settings_row = SiteSettings.load()
    settings_row.maintenance_mode = request.POST.get("maintenance_mode") == "1"
    settings_row.save(update_fields=["maintenance_mode"])
    if settings_row.maintenance_mode:
        messages.warning(request, "سایت برای کاربران در حالت تعمیر قرار گرفت.")
    else:
        messages.success(request, "سایت دوباره برای کاربران در دسترس است.")
    return redirect("admin:index")


_original_admin_get_urls = admin.site.get_urls
_original_admin_index = admin.site.index


def _cafe_admin_get_urls():
    extra = [
        path("site-maintenance/", admin.site.admin_view(toggle_maintenance), name="site_maintenance"),
    ]
    return extra + _original_admin_get_urls()


def _cafe_admin_index(request, extra_context=None):
    extra_context = extra_context or {}
    extra_context["maintenance_mode"] = SiteSettings.load().maintenance_mode
    return _original_admin_index(request, extra_context)


if not getattr(admin.site, "_cafe_maintenance_patched", False):
    admin.site.get_urls = _cafe_admin_get_urls
    admin.site.index = _cafe_admin_index
    admin.site._cafe_maintenance_patched = True
