from assistant.language import REASON_LINE
from assistant.models import (
    ACTION_APPROVE,
    ACTION_NEEDS_REVIEW,
    ACTION_REJECT,
    ACTION_REPLY,
    SCOPE_ADS,
    SCOPE_COMMENTS,
    SCOPE_TICKS,
    SCOPE_VENUES,
    ReviewPolicy,
)

DEFAULTS = {
    SCOPE_COMMENTS: {
        "instructions": (
            "نظر را از نظر فحاشی، کلمات رکیک، توهین، تهدید، اسپم، تبلیغ نامرتبط، محتوای جنسی یا نامناسب "
            "و لحن خصمانه بررسی کن. اگر نظر عادی و محترمانه است approve بده. "
            "اگر تخلف روشن است reject کن. اگر مبهم است needs_review بده. "
            "در صورت تأیید می‌توانی یک پاسخ کوتاه فارسی، محترمانه و تشکرآمیز در فیلد reply بنویسی. "
            f"{REASON_LINE}"
        ),
        "allowed_actions": [ACTION_APPROVE, ACTION_REJECT, ACTION_REPLY, ACTION_NEEDS_REVIEW],
        "auto_reply_enabled": False,
    },
    SCOPE_ADS: {
        "instructions": (
            "آگهی را از نظر کامل بودن فیلدها، محتوای نامناسب، اسپم و تبلیغ خلاف ضوابط بررسی کن. "
            "صحت مکان، شماره یا زمان را که قابل راستی‌آزمایی نیست فرض نکن. "
            "نقص اطلاعات یا مورد مشکوک را needs_review کن. "
            f"{REASON_LINE}"
        ),
        "allowed_actions": [ACTION_APPROVE, ACTION_REJECT, ACTION_NEEDS_REVIEW],
    },
    SCOPE_VENUES: {
        "instructions": (
            "درخواست ثبت کافه یا کلاب را از نظر کامل بودن نام، آدرس، تلفن و ساعات کاری و نبود محتوای نامناسب بررسی کن. "
            "مدرک یا صحت مکان را تأیید قطعی نکن. مورد ناقص یا مشکوک را needs_review کن. "
            f"{REASON_LINE}"
        ),
        "allowed_actions": [ACTION_APPROVE, ACTION_REJECT, ACTION_NEEDS_REVIEW],
    },
    SCOPE_TICKS: {
        "instructions": (
            "درخواست تیک طلایی را از نظر کامل بودن نام، تلفن و رزومه بررسی کن. "
            "هویت یا مدرک را تأیید نکن. تصمیم اعطای تیک طلایی با مدیر است؛ موارد حساس را needs_review بگذار. "
            f"{REASON_LINE}"
        ),
        "allowed_actions": [ACTION_NEEDS_REVIEW],
    },
}


def ensure_policies():
    for scope, data in DEFAULTS.items():
        policy, created = ReviewPolicy.objects.get_or_create(
            scope=scope,
            defaults={
                "instructions": data["instructions"],
                "allowed_actions": data["allowed_actions"],
                "auto_reply_enabled": data.get("auto_reply_enabled", False),
                "auto_enabled": True,
                "confidence_threshold": "0.85",
            },
        )
        fields = []
        if created:
            continue
        wanted = data["allowed_actions"]
        current = list(policy.allowed_actions or [])
        merged = list(dict.fromkeys(current + wanted))
        if merged != current:
            policy.allowed_actions = merged
            fields.append("allowed_actions")
        if REASON_LINE not in (policy.instructions or ""):
            policy.instructions = ((policy.instructions or "").rstrip() + "\n" + REASON_LINE).strip()
            fields.append("instructions")
        if fields:
            policy.save(update_fields=fields + ["updated_at"])
