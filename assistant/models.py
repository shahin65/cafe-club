from django.conf import settings
from django.db import models
from django.utils import timezone


def default_review_hours():
    return list(range(24))


def default_report_hours():
    return [0, 12]


SCOPE_COMMENTS = "comments"
SCOPE_ADS = "ads"
SCOPE_VENUES = "venues"
SCOPE_TICKS = "ticks"
SCOPES = (
    (SCOPE_COMMENTS, "نظرات کاربران"),
    (SCOPE_ADS, "آگهی‌ها"),
    (SCOPE_VENUES, "ثبت کافه و کلاب"),
    (SCOPE_TICKS, "درخواست تیک آبی"),
)

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_NEEDS_REVIEW = "needs_review"
STATUSES = (
    (STATUS_PENDING, "در انتظار بررسی"),
    (STATUS_APPROVED, "تأییدشده"),
    (STATUS_REJECTED, "ردشده"),
    (STATUS_NEEDS_REVIEW, "نیازمند بازبینی مدیر"),
)

ACTION_APPROVE = "approve"
ACTION_REJECT = "reject"
ACTION_REPLY = "reply"
ACTION_NEEDS_REVIEW = "needs_review"
ACTIONS = (ACTION_APPROVE, ACTION_REJECT, ACTION_REPLY, ACTION_NEEDS_REVIEW)
ACTION_CHOICES = (
    (ACTION_APPROVE, "تأیید"),
    (ACTION_REJECT, "رد"),
    (ACTION_REPLY, "پاسخ‌دهی"),
    (ACTION_NEEDS_REVIEW, "ارجاع برای بازبینی مدیر"),
)

SOURCE_SCENARIO_COMMENT = "scenario_comment"
SOURCE_VENUE_COMMENT = "venue_comment"
SOURCE_AD = "event_ad"
SOURCE_VENUE = "venue_submission"
SOURCE_TICK = "blue_tick"
SOURCES = (
    (SOURCE_SCENARIO_COMMENT, "نظر سناریو"),
    (SOURCE_VENUE_COMMENT, "نظر کافه"),
    (SOURCE_AD, "آگهی"),
    (SOURCE_VENUE, "ثبت کافه"),
    (SOURCE_TICK, "تیک آبی"),
)

KIND_HOURLY = "hourly"
KIND_REPORT = "report"
KIND_MANUAL = "manual"
RUN_KINDS = ((KIND_HOURLY, "ساعتی"), (KIND_REPORT, "گزارش"), (KIND_MANUAL, "دستی"))
RUN_RUNNING = "running"
RUN_DONE = "done"
RUN_ERROR = "error"


class AssistantConfig(models.Model):
    auto_paused = models.BooleanField("توقف همه اقدامات خودکار", default=False)
    review_hours = models.JSONField("ساعات بازبینی", default=default_review_hours, blank=True)
    report_hours = models.JSONField("ساعات ارسال گزارش", default=default_report_hours, blank=True)
    report_purchases = models.BooleanField("گزارش خریدهای جدید به بله", default=True)
    notes = models.TextField("یادداشت داخلی", blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="آخرین ویرایش‌کننده",
    )

    class Meta:
        verbose_name = "تنظیمات دستیار"
        verbose_name_plural = "تنظیمات دستیار"

    def __str__(self):
        return "تنظیمات دستیار هوش مصنوعی"

    @classmethod
    def load(cls):
        obj = cls.objects.order_by("id").first()
        if obj:
            return obj
        return cls.objects.create()


class ReviewPolicy(models.Model):
    scope = models.CharField("بخش", max_length=20, unique=True, choices=SCOPES)
    auto_enabled = models.BooleanField("بررسی خودکار فعال", default=True)
    realtime_review = models.BooleanField("رسیدگی بلادرنگ", default=False)
    realtime_report = models.BooleanField("گزارش بلادرنگ به بله", default=False)
    auto_reply_enabled = models.BooleanField("پاسخ‌دهی خودکار (فقط نظرات)", default=False)
    instructions = models.TextField("دستورالعمل و معیارهای بررسی", blank=True)
    confidence_threshold = models.DecimalField("آستانه اطمینان", max_digits=4, decimal_places=2, default=0.85)
    allowed_actions = models.JSONField("اقدام خودکار مجاز", default=list, blank=True)
    version = models.PositiveIntegerField("نسخه معیارها", default=1)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_review_policies",
    )

    class Meta:
        verbose_name = "معیار بررسی"
        verbose_name_plural = "معیارهای بررسی"

    def __str__(self):
        return self.get_scope_display()

    def allows(self, action):
        return action in (self.allowed_actions or [])

    def save(self, *args, **kwargs):
        if self.pk:
            previous = ReviewPolicy.objects.filter(pk=self.pk).first()
            if previous and (
                previous.instructions != self.instructions
                or previous.confidence_threshold != self.confidence_threshold
                or previous.allowed_actions != self.allowed_actions
                or previous.auto_enabled != self.auto_enabled
                or previous.auto_reply_enabled != self.auto_reply_enabled
            ):
                self.version = (previous.version or 1) + 1
        super().save(*args, **kwargs)


class ReviewCase(models.Model):
    source = models.CharField("منبع", max_length=32, choices=SOURCES, db_index=True)
    object_id = models.PositiveIntegerField("شناسه مورد")
    scope = models.CharField("بخش", max_length=20, choices=SCOPES, db_index=True)
    status = models.CharField("وضعیت", max_length=20, choices=STATUSES, default=STATUS_PENDING, db_index=True)
    submitted_at = models.DateTimeField("زمان ثبت مورد")
    title = models.CharField("خلاصه", max_length=200, blank=True)
    excerpt = models.TextField("متن مرتبط", blank=True)
    ai_decision = models.CharField("پیشنهاد هوش مصنوعی", max_length=20, choices=ACTION_CHOICES, blank=True)
    ai_reason = models.TextField("دلیل پیشنهاد", blank=True)
    ai_confidence = models.DecimalField("امتیاز اطمینان", max_digits=4, decimal_places=2, null=True, blank=True)
    ai_reply = models.TextField("پاسخ پیشنهادی", blank=True)
    reply_sent = models.BooleanField("پاسخ ارسال شده", default=False)
    policy_version = models.PositiveIntegerField("نسخه معیار", null=True, blank=True)
    applied_action = models.CharField("اقدام انجام‌شده", max_length=20, blank=True)
    applied_at = models.DateTimeField("زمان اقدام", null=True, blank=True)
    manager_note = models.TextField("توضیح مدیر", blank=True)
    manager_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assistant_reviews",
    )
    manager_at = models.DateTimeField(null=True, blank=True)
    processing = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=240, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def display_reason(self):
        from assistant.language import persian_reason

        return persian_reason(self.ai_reason)

    class Meta:
        verbose_name = "مورد بررسی"
        verbose_name_plural = "موارد بررسی"
        unique_together = (("source", "object_id"),)
        ordering = ["-submitted_at", "-id"]

    def __str__(self):
        return f"{self.get_source_display()} #{self.object_id}"

    def mark_error(self, message):
        self.retry_count = (self.retry_count or 0) + 1
        self.last_error = (message or "")[:240]
        self.processing = False
        self.locked_at = None
        self.save(update_fields=["retry_count", "last_error", "processing", "locked_at", "updated_at"])


class ReviewEvent(models.Model):
    case = models.ForeignKey(ReviewCase, on_delete=models.CASCADE, related_name="events")
    actor = models.CharField("عامل", max_length=20)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    decision = models.CharField("نتیجه", max_length=20)
    reason = models.TextField(blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    action = models.CharField("اقدام", max_length=20, blank=True)
    applied = models.BooleanField(default=False)
    dry_run = models.BooleanField(default=False)
    policy_version = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def display_reason(self):
        from assistant.language import persian_reason

        return persian_reason(self.reason)

    class Meta:
        verbose_name = "سابقه بررسی"
        verbose_name_plural = "سوابق بررسی"
        ordering = ["-created_at", "-id"]


class AssistantRun(models.Model):
    kind = models.CharField(max_length=20, choices=RUN_KINDS)
    status = models.CharField(max_length=20, default=RUN_RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-started_at"]


class BaleReport(models.Model):
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    payload = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=240, blank=True)

    class Meta:
        unique_together = (("period_start", "period_end"),)
        ordering = ["-period_start"]
