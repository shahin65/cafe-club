from django.contrib import admin
from django.utils.html import format_html

from .models import Banner


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
