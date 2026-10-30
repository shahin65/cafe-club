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


def allocate_six_digit_id(used):
    used = set(used)
    for _ in range(200):
        candidate = random.randint(100000, 999999)
        if candidate not in used:
            return candidate
    raise ValidationError("شناسه جدیدی ساخته نشد.")


def allocate_public_id():
    used = set(UserProfile.objects.values_list("public_id", flat=True))
    return allocate_six_digit_id(used)


def allocate_venue_public_id():
    used = set(Venue.objects.exclude(public_id=None).values_list("public_id", flat=True))
    return allocate_six_digit_id(used)


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="club_profile",
        verbose_name="کاربر",
    )
    public_id = models.PositiveIntegerField("شناسه شش‌رقمی", unique=True)
    display_name = models.CharField(
        "نام نمایشی",
        max_length=40,
        blank=True,
        help_text="اگر پر شود، این نام به‌جای نام کاربری به خود کاربر و دیگران نشان داده می‌شود.",
    )
    is_verified = models.BooleanField("تیک آبی", default=False)
    is_blocked = models.BooleanField(
        "مسدود",
        default=False,
        help_text="اگر فعال باشد این کاربر نمی‌تواند دوباره وارد حساب شود.",
    )
    bio = models.CharField("بیوگرافی", max_length=280, blank=True)
    photo = models.ImageField("عکس پروفایل", upload_to="profiles", blank=True)
    google_email = models.EmailField("جیمیل متصل", blank=True, null=True, unique=True)
    google_sub = models.CharField("شناسه گوگل", max_length=64, blank=True, null=True, unique=True)
    home_scenario_ids = models.JSONField(
        "سناریوهای صفحه اصلی",
        default=list,
        blank=True,
        help_text="حداکثر ۶ سناریوی پین‌شده برای بخش تقسیم نقش سریع.",
    )
    APP_DIRECT = "direct"
    APP_BAZAAR = "bazaar"
    APP_MYKET = "myket"
    APP_SOURCE_CHOICES = [
        ("", "وب / نامشخص"),
        (APP_DIRECT, "نسخه دایرکت"),
        (APP_BAZAAR, "کافه بازار"),
        (APP_MYKET, "مایکت"),
    ]
    app_source = models.CharField(
        "منبع اپلیکیشن",
        max_length=12,
        choices=APP_SOURCE_CHOICES,
        blank=True,
        default="",
        help_text="اگر کاربر از لینک رفرال نسخه دایرکت، بازار یا مایکت وارد شده باشد اینجا ثبت می‌شود.",
    )

    class Meta:
        verbose_name = "تیک آبی"
        verbose_name_plural = "تیک آبی"
        ordering = ["public_id"]

    def __str__(self):
        return f"{self.public_id} — {self.user.get_username()}"

    def public_id_display(self):
        return f"{self.public_id:06d}"

    public_id_display.short_description = "شناسه"

    def shown_name(self):
        name = (self.display_name or "").strip()
        if name:
            return name
        return self.user.get_username()

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
    event_at = models.DateTimeField("زمان برگزاری", null=True, blank=True, db_index=True)
    phone = models.CharField("تلفن تماس ایونت‌گذار", max_length=30)
    ticket_price = models.CharField("قیمت ورودی", max_length=80)
    cafe_bank = models.CharField("بانک کافه", max_length=120)
    city = models.CharField("شهر", max_length=80, default="")
    district = models.CharField("محدوده", max_length=120, default="")
    scenario = models.CharField("سناریو", max_length=120, default="")
    created_at = models.DateTimeField("زمان ثبت", auto_now_add=True)
    expires_at = models.DateTimeField("پایان نمایش رایگان")
    is_published = models.BooleanField("منتشر شده", default=True)
    is_new = models.BooleanField("جدید برای ادمین", default=True)
    is_boosted = models.BooleanField("نردبان‌شده", default=False, db_index=True)
    boosted_at = models.DateTimeField("زمان نردبان", null=True, blank=True, db_index=True)
    boost_requested = models.BooleanField("درخواست نردبان", default=False)
    boost_channel = models.CharField(
        "منبع پرداخت نردبان",
        max_length=12,
        blank=True,
        help_text="برای اتصال بعدی درگاه بر اساس رفرال دایرکت، بازار یا مایکت.",
    )
    promo_plan = models.CharField("پلن تبلیغاتی", max_length=12, blank=True, db_index=True)
    pending_plan = models.CharField("پلن در انتظار پرداخت", max_length=12, blank=True)
    promo_rank = models.PositiveSmallIntegerField("رتبه پلن", default=0, db_index=True)
    show_on_home = models.BooleanField("نمایش در صفحه اصلی", default=False, db_index=True)
    latitude = models.DecimalField("عرض جغرافیایی", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("طول جغرافیایی", max_digits=9, decimal_places=6, null=True, blank=True)
    photo_1 = models.ImageField("تصویر اضافه ۱", upload_to="event_ads/gallery", blank=True)
    photo_2 = models.ImageField("تصویر اضافه ۲", upload_to="event_ads/gallery", blank=True)
    photo_3 = models.ImageField("تصویر اضافه ۳", upload_to="event_ads/gallery", blank=True)

    class Meta:
        verbose_name = "آگهی"
        verbose_name_plural = "آگهی‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return self.event_name

    def is_live(self):
        from django.utils import timezone

        return self.is_published and self.expires_at > timezone.now()

    def advertiser_name(self):
        profile = getattr(self.user, "club_profile", None)
        if profile:
            return profile.shown_name()
        return self.user.get_username()

    def when_display(self):
        from banners.jalali import format_jalali_datetime

        if self.event_at:
            return format_jalali_datetime(self.event_at)
        return self.starts_at

    def date_display(self):
        from banners.jalali import format_jalali_date

        if self.event_at:
            return format_jalali_date(self.event_at)
        return self.starts_at

    def weekday_display(self):
        from banners.jalali import format_jalali_weekday

        if self.event_at:
            return format_jalali_weekday(self.event_at)
        return ""

    def time_display(self):
        from banners.jalali import format_jalali_time

        if self.event_at:
            return format_jalali_time(self.event_at)
        return ""

    def is_laddered(self):
        return bool(self.is_boosted)

    def plan_label(self):
        from banners.promo import PLANS

        plan = PLANS.get(self.promo_plan) or {}
        return plan.get("title") or ""

    def plan_badge(self):
        title = self.plan_label()
        if title:
            return f"نردبان {title}"
        if self.is_boosted:
            return "نردبان‌شده"
        return ""

    def has_nav(self):
        return self.promo_rank >= 2 and self.latitude is not None and self.longitude is not None

    def allows_extras(self):
        return self.promo_rank >= 2

    def gallery(self):
        return [image for image in (self.photo_1, self.photo_2, self.photo_3) if image]


class EventAdLike(models.Model):
    ad = models.ForeignKey(EventAd, on_delete=models.CASCADE, related_name="likes", verbose_name="آگهی")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_ad_likes",
        null=True,
        blank=True,
        verbose_name="کاربر",
    )
    guest_key = models.CharField("کلید مهمان", max_length=64, blank=True)
    created_at = models.DateTimeField("زمان", auto_now_add=True)

    class Meta:
        verbose_name = "لایک آگهی"
        verbose_name_plural = "لایک‌های آگهی"

    def __str__(self):
        return str(self.ad_id)


class Venue(models.Model):
    name = models.CharField("اسم کلاب", max_length=120)
    public_id = models.PositiveIntegerField("شناسه شش‌رقمی", unique=True, db_index=True)
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
    promo_plan = models.CharField("پلن تبلیغاتی", max_length=12, blank=True, db_index=True)
    pending_plan = models.CharField("پلن در انتظار پرداخت", max_length=12, blank=True)
    promo_rank = models.PositiveSmallIntegerField("رتبه پلن", default=0, db_index=True)
    show_on_home = models.BooleanField("نمایش در صفحه اصلی", default=False, db_index=True)
    promo_expires_at = models.DateTimeField("پایان پلن تبلیغاتی", null=True, blank=True, db_index=True)
    boosted_at = models.DateTimeField("زمان نردبان", null=True, blank=True, db_index=True)
    boost_requested = models.BooleanField("درخواست نردبان", default=False)
    boost_channel = models.CharField("منبع پرداخت نردبان", max_length=12, blank=True)

    class Meta:
        verbose_name = "کافه / کلاب"
        verbose_name_plural = "کافه‌ها و کلاب‌ها"
        ordering = ["city", "name"]

    def __str__(self):
        return self.name

    def public_id_display(self):
        return f"{self.public_id:06d}"

    public_id_display.short_description = "شناسه"

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = allocate_venue_public_id()
        super().save(*args, **kwargs)

    def has_point(self):
        return self.latitude is not None and self.longitude is not None

    def maps_point(self):
        if not self.has_point():
            return None
        return float(self.latitude), float(self.longitude)

    def gallery(self):
        return [image for image in (self.photo_1, self.photo_2, self.photo_3) if image]

    def cover_image(self):
        if self.logo:
            return self.logo
        photos = self.gallery()
        return photos[0] if photos else None

    def is_promo_live(self):
        from django.utils import timezone

        return bool(
            self.is_active
            and self.promo_plan
            and self.promo_expires_at
            and self.promo_expires_at > timezone.now()
        )

    def promo_badge(self):
        from banners.promo import VENUE_PLANS

        plan = VENUE_PLANS.get(self.promo_plan) or {}
        title = plan.get("title") or ""
        if title:
            return f"نردبان {title} کلاب"
        return ""


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
    latitude = models.DecimalField("عرض جغرافیایی", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("طول جغرافیایی", max_digits=9, decimal_places=6, null=True, blank=True)
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


class SiteSettings(models.Model):
    maintenance_mode = models.BooleanField(
        "اپلیکیشن در دست تعمیر است",
        default=False,
        help_text="اگر فعال باشد سایت برای کاربران عادی بسته می‌شود تا زمان به‌روزرسانی.",
    )

    class Meta:
        verbose_name = "وضعیت سایت"
        verbose_name_plural = "وضعیت سایت"

    def __str__(self):
        return "در دست تعمیر" if self.maintenance_mode else "فعال"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class LegalPage(models.Model):
    KEY_PRIVACY = "privacy"
    KEY_TERMS = "terms"
    KEY_CHOICES = [
        (KEY_PRIVACY, "سیاست حفظ حریم خصوصی"),
        (KEY_TERMS, "شرایط استفاده از خدمات"),
    ]
    key = models.CharField("شناسه", max_length=20, unique=True, choices=KEY_CHOICES)
    title = models.CharField("عنوان فارسی", max_length=120)
    title_en = models.CharField("عنوان انگلیسی", max_length=120, blank=True)
    body = models.TextField("متن فارسی", blank=True)
    body_en = models.TextField("متن انگلیسی", blank=True)

    class Meta:
        verbose_name = "صفحه حقوقی"
        verbose_name_plural = "صفحات حقوقی"
        ordering = ["key"]

    def __str__(self):
        return self.title

    def display_title(self):
        if (get_language() or "fa").startswith("en"):
            return self.title_en or self.title
        return self.title or self.title_en

    def display_body(self):
        if (get_language() or "fa").startswith("en"):
            return self.body_en or self.body
        return self.body or self.body_en


class Tournament(models.Model):
    STATUS_READY = "ready"
    STATUS_ACTIVE = "active"
    STATUS_CHOICES = [
        (STATUS_READY, "آماده شروع"),
        (STATUS_ACTIVE, "در حال برگزاری"),
    ]
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tournaments",
        null=True,
        blank=True,
        verbose_name="کاربر",
    )
    guest_key = models.CharField("کلید مهمان", max_length=64, blank=True, db_index=True)
    name = models.CharField("نام تورنومنت", max_length=120)
    prizes = models.JSONField("جوایز", default=list)
    status = models.CharField("وضعیت", max_length=20, choices=STATUS_CHOICES, default=STATUS_READY, db_index=True)
    created_at = models.DateTimeField("زمان ساخت", auto_now_add=True)
    ended_at = models.DateTimeField("پایان تورنومنت", null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "تورنومنت"
        verbose_name_plural = "تورنومنت‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def prize_count(self):
        return len(self.prizes or [])

    def active_players(self):
        return self.players.filter(is_active=True).order_by("id")

    def winners(self):
        return self.players.filter(place__isnull=False).order_by("place")

    def can_manage(self, request):
        if self.owner_id:
            return request.user.is_authenticated and request.user.id == self.owner_id
        key = request.session.get("custom_guest_key") or ""
        return bool(key) and key == self.guest_key

    def latest_round(self, number=None):
        if number is None:
            return self.rounds.order_by("-number").first()
        return self.rounds.filter(number=number).first()

    def is_open(self):
        return self.ended_at is None

    def last_kind(self):
        last = self.latest_round()
        return getattr(last, "kind", "") if last else ""


class TournamentPlayer(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="players", verbose_name="تورنومنت")
    name = models.CharField("نام", max_length=80)
    is_active = models.BooleanField("حاضر", default=True)
    place = models.PositiveSmallIntegerField("رتبه", null=True, blank=True)

    class Meta:
        verbose_name = "شرکت‌کننده تورنومنت"
        verbose_name_plural = "شرکت‌کنندگان تورنومنت"
        ordering = ["id"]

    def __str__(self):
        return self.name


class TournamentRound(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="rounds", verbose_name="تورنومنت")
    KIND_ROUND1 = "round1"
    KIND_ROUND2 = "round2"
    KIND_SEMI = "semi"
    KIND_FINAL = "final"
    KIND_CHOICES = [
        (KIND_ROUND1, "دور اول"),
        (KIND_ROUND2, "دور دوم"),
        (KIND_SEMI, "نیمه نهایی"),
        (KIND_FINAL, "فینال"),
    ]
    number = models.PositiveSmallIntegerField("شماره دور")
    kind = models.CharField("نوع دور", max_length=12, choices=KIND_CHOICES, default=KIND_ROUND1)
    title = models.CharField("عنوان", max_length=40)
    group_count = models.PositiveSmallIntegerField("تعداد گروه", default=1)
    group_size = models.PositiveSmallIntegerField("نفر در گروه", default=1)
    is_final = models.BooleanField("دور پایانی", default=False)
    created_at = models.DateTimeField("زمان قرعه", auto_now_add=True)

    class Meta:
        verbose_name = "دور تورنومنت"
        verbose_name_plural = "دورهای تورنومنت"
        unique_together = ("tournament", "number")
        ordering = ["number"]

    def __str__(self):
        return f"{self.tournament} — {self.title}"

    def grouped_seats(self):
        groups = []
        seats = list(self.seats.select_related("player").order_by("group_index", "seat_number"))
        current = None
        for seat in seats:
            if current is None or current["index"] != seat.group_index:
                current = {"index": seat.group_index, "seats": []}
                groups.append(current)
            current["seats"].append(seat)
        return groups


class TournamentSeat(models.Model):
    round = models.ForeignKey(TournamentRound, on_delete=models.CASCADE, related_name="seats", verbose_name="دور")
    player = models.ForeignKey(TournamentPlayer, on_delete=models.CASCADE, related_name="seats", verbose_name="بازیکن")
    group_index = models.PositiveSmallIntegerField("گروه")
    seat_number = models.PositiveSmallIntegerField("صندلی")

    class Meta:
        verbose_name = "صندلی تورنومنت"
        verbose_name_plural = "صندلی‌های تورنومنت"
        ordering = ["group_index", "seat_number"]

    def __str__(self):
        return f"{self.player} — گروه {self.group_index} صندلی {self.seat_number}"

