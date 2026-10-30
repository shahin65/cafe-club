from assistant.models import (
    ACTION_NEEDS_REVIEW,
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
            "در صورت تأیید می‌توانی یک پاسخ کوتاه فارسی، محترمانه و تشکرآمیز در فیلد reply بنویسی."
        ),
        "allowed_actions": [ACTION_NEEDS_REVIEW],
        "auto_reply_enabled": False,
    },
    SCOPE_ADS: {
        "instructions": (
            "آگهی را از نظر کامل بودن فیلدها، محتوای نامناسب، اسپم و تبلیغ خلاف ضوابط بررسی کن. "
            "صحت مکان، شماره یا زمان را که قابل راستی‌آزمایی نیست فرض نکن. "
            "نقص اطلاعات یا مورد مشکوک را needs_review کن."
        ),
        "allowed_actions": [ACTION_NEEDS_REVIEW],
    },
    SCOPE_VENUES: {
        "instructions": (
            "درخواست ثبت کافه یا کلاب را از نظر کامل بودن نام، آدرس، تلفن و ساعات کاری و نبود محتوای نامناسب بررسی کن. "
            "مدرک یا صحت مکان را تأیید قطعی نکن. مورد ناقص یا مشکوک را needs_review کن."
        ),
        "allowed_actions": [ACTION_NEEDS_REVIEW],
    },
    SCOPE_TICKS: {
        "instructions": (
            "درخواست تیک آبی را از نظر کامل بودن نام، تلفن و بیوگرافی بررسی کن. "
            "هویت یا مدرک را تأیید نکن. تصمیم اعطای تیک آبی با مدیر است؛ موارد حساس را needs_review بگذار."
        ),
        "allowed_actions": [ACTION_NEEDS_REVIEW],
    },
}


def ensure_policies():
    for scope, data in DEFAULTS.items():
        ReviewPolicy.objects.get_or_create(
            scope=scope,
            defaults={
                "instructions": data["instructions"],
                "allowed_actions": data["allowed_actions"],
                "auto_reply_enabled": data.get("auto_reply_enabled", False),
                "auto_enabled": True,
                "confidence_threshold": "0.85",
            },
        )
