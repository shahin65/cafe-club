from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import get_language


class Banner(models.Model):
    title_fa = models.CharField(
        "عنوان فارسی",
        max_length=200,
        error_messages={
            "blank": "عنوان فارسی را وارد کنید.",
            "max_length": "عنوان فارسی نباید بیشتر از ۲۰۰ نویسه باشد.",
        },
    )
    title_en = models.CharField(
        "عنوان انگلیسی",
        max_length=200,
        error_messages={
            "blank": "عنوان انگلیسی را وارد کنید.",
            "max_length": "عنوان انگلیسی نباید بیشتر از ۲۰۰ نویسه باشد.",
        },
    )
    description_fa = models.TextField(
        "توضیحات فارسی",
        blank=True,
        help_text="متن کوتاهی که زیر عنوان فارسی در سایت دیده می‌شود.",
    )
    description_en = models.TextField(
        "توضیحات انگلیسی",
        blank=True,
        help_text="متن کوتاه انگلیسی برای بازدیدکنندگانی که زبان سایت را انگلیسی کرده‌اند.",
    )
    external_url = models.URLField(
        "نشانی بیرونی",
        blank=True,
        help_text="پیوند کامل بیرون از سایت، مانند https://example.com",
        error_messages={"invalid": "نشانی بیرونی معتبر نیست. یک نشانی کامل با http یا https وارد کنید."},
    )
    internal_url = models.CharField(
        "نشانی صفحه داخلی",
        max_length=300,
        blank=True,
        help_text="مسیر یکی از صفحه‌های خود برنامه. باید با / شروع شود، مانند /nights/",
        error_messages={
            "max_length": "نشانی صفحه داخلی نباید بیشتر از ۳۰۰ نویسه باشد.",
        },
    )
    is_active = models.BooleanField(
        "فعال",
        default=True,
        help_text="بنر غیرفعال در سایت نمایش داده نمی‌شود.",
    )
    display_order = models.PositiveIntegerField(
        "ترتیب نمایش",
        default=0,
        help_text="عدد کوچکتر زودتر نشان داده می‌شود. ترتیب پیش‌فرض بنرها ۱ تا ۴ است.",
        error_messages={
            "invalid": "ترتیب نمایش باید یک عدد درست باشد.",
        },
    )
    image = models.ImageField(
        "تصویر بنر",
        upload_to="banners",
        help_text="فایل تصویر بنر. نام فایل‌های اولیه Banner1 تا Banner4 است.",
        error_messages={
            "blank": "تصویر بنر را انتخاب کنید.",
            "invalid": "فایل انتخاب‌شده یک تصویر معتبر نیست.",
            "invalid_image": "فایل انتخاب‌شده یک تصویر معتبر نیست.",
        },
    )

    class Meta:
        verbose_name = "بنر"
        verbose_name_plural = "بنرها"
        ordering = ["display_order", "pk"]

    def __str__(self):
        return self.title_fa or self.title_en or "بنر"

    def clean(self):
        super().clean()
        internal = (self.internal_url or "").strip()
        self.internal_url = internal
        if internal and "://" in internal:
            raise ValidationError(
                {"internal_url": "برای پیوند بیرون از سایت، فیلد نشانی بیرونی را پر کنید."}
            )
        if internal and not internal.startswith("/"):
            raise ValidationError(
                {"internal_url": "نشانی صفحه داخلی باید با / شروع شود. نمونه: /games/"}
            )

    def title_for_current_language(self):
        if (get_language() or "fa").startswith("en"):
            return self.title_en or self.title_fa
        return self.title_fa or self.title_en

    def description_for_current_language(self):
        if (get_language() or "fa").startswith("en"):
            return self.description_en or self.description_fa
        return self.description_fa or self.description_en

    def public_url(self):
        if self.external_url:
            return self.external_url
        return self.localized_internal_url()

    def opens_externally(self):
        return bool(self.external_url)

    def localized_internal_url(self):
        path = (self.internal_url or "").strip()
        if not path:
            return ""
        if not path.startswith("/"):
            path = f"/{path}"
        language = (get_language() or settings.LANGUAGE_CODE).split("-")[0]
        language_codes = {code for code, _name in settings.LANGUAGES}
        parts = path.split("/")
        if len(parts) > 1 and parts[1] in language_codes:
            remainder = "/".join(parts[2:])
            path = f"/{remainder}" if remainder else "/"
        if language != settings.LANGUAGE_CODE:
            if path == "/":
                return f"/{language}/"
            return f"/{language}{path}"
        return path
