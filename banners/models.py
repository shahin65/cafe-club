import random

from django.conf import settings
from django.contrib.auth.models import User
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


def allocate_public_id():
    used = set(UserProfile.objects.values_list("public_id", flat=True))
    for _ in range(200):
        candidate = random.randint(100000, 999999)
        if candidate not in used:
            return candidate
    raise ValidationError("شناسه جدیدی برای کاربر ساخته نشد.")


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="club_profile",
        verbose_name="کاربر",
    )
    public_id = models.PositiveIntegerField("شناسه شش‌رقمی", unique=True)
    is_verified = models.BooleanField("تیک آبی", default=False)
    bio = models.CharField("بیوگرافی", max_length=280, blank=True)
    photo = models.ImageField("عکس پروفایل", upload_to="profiles", blank=True)
    google_email = models.EmailField("جیمیل متصل", blank=True, null=True, unique=True)
    google_sub = models.CharField("شناسه گوگل", max_length=64, blank=True, null=True, unique=True)

    class Meta:
        verbose_name = "تیک آبی"
        verbose_name_plural = "تیک آبی"
        ordering = ["public_id"]

    def __str__(self):
        return f"{self.public_id} — {self.user.get_username()}"

    def public_id_display(self):
        return f"{self.public_id:06d}"

    public_id_display.short_description = "شناسه"

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = allocate_public_id()
        if self.google_email:
            self.google_email = self.google_email.strip().lower()
        super().save(*args, **kwargs)


class BlueTickRequest(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blue_tick_requests",
        verbose_name="کاربر",
    )
    full_name = models.CharField("نام و نام خانوادگی", max_length=80)
    phone = models.CharField("شماره تماس", max_length=20)
    biography = models.TextField("بیوگرافی")
    created_at = models.DateTimeField("زمان ارسال", auto_now_add=True)
    is_reviewed = models.BooleanField("بررسی شده", default=False)

    class Meta:
        verbose_name = "درخواست تیک آبی"
        verbose_name_plural = "درخواست‌های تیک آبی"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.user.get_username()}"


class EventAd(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_ads",
        verbose_name="کاربر",
    )
    event_name = models.CharField("نام ایونت", max_length=120)
    organizer_name = models.CharField("نام ایونت‌گذار", max_length=80)
    image = models.ImageField("تصویر ایونت", upload_to="event_ads")
    address = models.CharField("آدرس ایونت", max_length=300)
    starts_at = models.CharField("ساعت برگزاری ایونت", max_length=80)
    phone = models.CharField("تلفن تماس ایونت‌گذار", max_length=30)
    ticket_price = models.CharField("قیمت ورودی", max_length=80)
    cafe_bank = models.CharField("بانک کافه", max_length=120)
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    expires_at = models.DateTimeField("پایان نمایش رایگان")
    is_published = models.BooleanField("منتشر شده", default=True)
    is_new = models.BooleanField("جدید برای ادمین", default=True)

    class Meta:
        verbose_name = "آگهی"
        verbose_name_plural = "آگهی‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return self.event_name

    def is_live(self):
        from django.utils import timezone

        return self.is_published and self.expires_at > timezone.now()


class Venue(models.Model):
    name = models.CharField("اسم کلاب", max_length=120)
    city = models.CharField("شهر", max_length=80, db_index=True)
    logo = models.ImageField("لوگو", upload_to="venues/logos", blank=True)
    manager_name = models.CharField("نام مدیر یا سوپروایزر", max_length=80, blank=True)
    photo_1 = models.ImageField("تصویر ۱", upload_to="venues/photos", blank=True)
    photo_2 = models.ImageField("تصویر ۲", upload_to="venues/photos", blank=True)
    photo_3 = models.ImageField("تصویر ۳", upload_to="venues/photos", blank=True)
    hours = models.CharField(
        "روزها و ساعات کاری",
        max_length=200,
        blank=True,
        help_text="نمونه: شنبه تا چهارشنبه ۱۶ تا ۲۴",
    )
    address = models.CharField("آدرس", max_length=300)
    phone = models.CharField("تلفن تماس", max_length=30, blank=True)
    latitude = models.DecimalField("عرض جغرافیایی", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("طول جغرافیایی", max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "کافه / کلاب"
        verbose_name_plural = "کافه‌ها و کلاب‌ها"
        ordering = ["city", "name"]

    def __str__(self):
        return self.name

    def has_point(self):
        return self.latitude is not None and self.longitude is not None

    def maps_point(self):
        if not self.has_point():
            return None
        return float(self.latitude), float(self.longitude)

    def gallery(self):
        return [image for image in (self.photo_1, self.photo_2, self.photo_3) if image]


class VenueRating(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="ratings", verbose_name="کافه / کلاب")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="venue_ratings",
        null=True,
        blank=True,
        verbose_name="کاربر",
    )
    guest_key = models.CharField("کلید مهمان", max_length=64, blank=True)
    stars = models.PositiveSmallIntegerField("امتیاز")
    created_at = models.DateTimeField("زمان", auto_now_add=True)
    updated_at = models.DateTimeField("به‌روزرسانی", auto_now=True)

    class Meta:
        verbose_name = "امتیاز کافه"
        verbose_name_plural = "امتیازهای کافه"
        constraints = [
            models.UniqueConstraint(
                fields=["venue", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_venue_rating_user",
            ),
            models.UniqueConstraint(
                fields=["venue", "guest_key"],
                condition=models.Q(user__isnull=True),
                name="unique_venue_rating_guest",
            ),
        ]

    def __str__(self):
        return f"{self.venue} — {self.stars}"

    def clean(self):
        super().clean()
        if self.stars not in {1, 2, 3, 4, 5}:
            raise ValidationError({"stars": "امتیاز باید بین ۱ تا ۵ ستاره باشد."})


class VenueComment(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="comments", verbose_name="کافه / کلاب")
    author_name = models.CharField("نام", max_length=40)
    body = models.TextField("نظر", max_length=1000)
    is_approved = models.BooleanField("تأیید شده", default=False)
    created_at = models.DateTimeField("زمان ارسال", auto_now_add=True)

    class Meta:
        verbose_name = "نظر کافه / کلاب"
        verbose_name_plural = "نظرات کاربران در رابطه با کافه کلاب‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author_name}: {self.body[:40]}"


class VenueSubmission(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="venue_submissions",
        null=True,
        blank=True,
        verbose_name="کاربر",
    )
    name = models.CharField("نام کلاب", max_length=120)
    logo = models.ImageField("لوگو", upload_to="venue_submissions/logos")
    photo_1 = models.ImageField("تصویر ۱", upload_to="venue_submissions/photos", blank=True)
    photo_2 = models.ImageField("تصویر ۲", upload_to="venue_submissions/photos", blank=True)
    photo_3 = models.ImageField("تصویر ۳", upload_to="venue_submissions/photos", blank=True)
    manager_name = models.CharField("نام مدیر یا سوپروایزر مجموعه", max_length=80)
    address = models.CharField("آدرس", max_length=300)
    phone = models.CharField("تلفن", max_length=30)
    hours = models.CharField("روزها و ساعات کاری", max_length=200)
    city = models.CharField("شهر", max_length=80, blank=True, help_text="برای ثبت نهایی در لیست، شهر را اینجا وارد کنید.")
    is_reviewed = models.BooleanField("بررسی شده", default=False)
    created_at = models.DateTimeField("زمان ارسال", auto_now_add=True)

    class Meta:
        verbose_name = "درخواست ثبت کافه / کلاب"
        verbose_name_plural = "درخواست‌های ثبت کافه و کلاب"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class SiteLink(models.Model):
    GROUP_DOWNLOAD = "download"
    GROUP_SOCIAL = "social"
    GROUP_CHOICES = [
        (GROUP_DOWNLOAD, "دانلود اپلیکیشن"),
        (GROUP_SOCIAL, "شبکه‌های اجتماعی"),
    ]
    KEY_ANDROID = "android"
    KEY_IOS = "ios"
    KEY_BAZAAR = "bazaar"
    KEY_MYKET = "myket"
    KEY_INSTAGRAM = "instagram"
    KEY_TELEGRAM = "telegram"
    KEY_WHATSAPP = "whatsapp"
    KEY_RUBIKA = "rubika"
    KEY_CHOICES = [
        (KEY_ANDROID, "اندروید"),
        (KEY_IOS, "آیفون"),
        (KEY_BAZAAR, "کافه بازار"),
        (KEY_MYKET, "مایکت"),
        (KEY_INSTAGRAM, "اینستاگرام"),
        (KEY_TELEGRAM, "تلگرام"),
        (KEY_WHATSAPP, "واتس‌اپ"),
        (KEY_RUBIKA, "روبیکا"),
    ]
    group = models.CharField("گروه", max_length=20, choices=GROUP_CHOICES)
    key = models.CharField("شناسه", max_length=20, unique=True, choices=KEY_CHOICES)
    title = models.CharField("عنوان فارسی", max_length=80)
    title_en = models.CharField("عنوان انگلیسی", max_length=80, blank=True)
    url = models.URLField("لینک", blank=True, help_text="اگر خالی باشد در صفحه تنظیمات نشان داده نمی‌شود.")
    image = models.ImageField("آیکون / تصویر", upload_to="site_links", blank=True)
    is_active = models.BooleanField("فعال", default=True)
    sort_order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        verbose_name = "تنظیم"
        verbose_name_plural = "تنظیمات"
        ordering = ["group", "sort_order", "id"]

    def __str__(self):
        return self.title

    def display_title(self):
        if (get_language() or "fa").startswith("en"):
            return self.title_en or self.title
        return self.title or self.title_en
