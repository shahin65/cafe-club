from datetime import timedelta

PLAN_FREE = "free"
PLAN_BRONZE = "bronze"
PLAN_SILVER = "silver"
PLAN_GOLD = "gold"
FREE_LIFE_HOURS = 12

PLANS = {
    PLAN_BRONZE: {
        "key": PLAN_BRONZE,
        "title": "برنزی",
        "price": 100_000,
        "price_label": "۱۰۰ هزار تومان",
        "rank": 1,
        "needs_extras": False,
        "show_on_home": False,
        "extra_days": 4,
        "features": (
            "نردبان در فهرست آگهی‌ها",
            "۴ روز نمایش اضافه پس از زمان برگزاری",
        ),
    },
    PLAN_SILVER: {
        "key": PLAN_SILVER,
        "title": "نقره‌ای",
        "price": 200_000,
        "price_label": "۲۰۰ هزار تومان",
        "rank": 2,
        "needs_extras": True,
        "show_on_home": False,
        "extra_days": 5,
        "features": (
            "نردبان در فهرست آگهی‌ها",
            "۵ روز نمایش اضافه پس از زمان برگزاری",
            "مسیریاب محل برگزاری",
            "تا سه تصویر اضافه",
        ),
    },
    PLAN_GOLD: {
        "key": PLAN_GOLD,
        "title": "طلایی",
        "price": 250_000,
        "price_label": "۲۵۰ هزار تومان",
        "rank": 3,
        "needs_extras": True,
        "show_on_home": True,
        "extra_days": 7,
        "features": (
            "نردبان در فهرست آگهی‌ها",
            "یک هفته نمایش اضافه پس از زمان برگزاری",
            "مسیریاب محل برگزاری",
            "تا سه تصویر اضافه",
            "نمایش در صفحه اصلی اپ",
        ),
    },
}

FREE_PLAN = {
    "key": PLAN_FREE,
    "title": "رایگان",
    "price": 0,
    "price_label": "بدون هزینه",
    "rank": 0,
    "needs_extras": False,
    "show_on_home": False,
    "extra_days": 0,
    "features": (f"نمایش تا {FREE_LIFE_HOURS} ساعت پس از زمان برگزاری",),
}

CREATE_PLANS = (FREE_PLAN, PLANS[PLAN_BRONZE], PLANS[PLAN_SILVER], PLANS[PLAN_GOLD])

PLAN_CHOICES = (
    ("", "بدون پلن"),
    (PLAN_BRONZE, "برنزی"),
    (PLAN_SILVER, "نقره‌ای"),
    (PLAN_GOLD, "طلایی"),
)


def plan_or_none(value):
    if value in PLANS:
        return value
    return None


def create_plan_key(value):
    raw = (value or "").strip()
    if raw in ("", PLAN_FREE):
        return None
    return plan_or_none(raw)


def plan_display_delta(plan_key=None):
    plan = PLANS.get(plan_key or "")
    if plan:
        return timedelta(days=plan["extra_days"])
    return timedelta(hours=FREE_LIFE_HOURS)


def plan_expires_at(event_at, plan_key=None):
    return event_at + plan_display_delta(plan_key)


VENUE_PLANS = {
    PLAN_BRONZE: {
        "key": PLAN_BRONZE,
        "title": "برنزی",
        "price": 250_000,
        "price_label": "۲۵۰ هزار تومان",
        "rank": 1,
        "days": 7,
        "show_on_home": False,
        "features": (
            "یک هفته نردبان در بالاترین قسمت آگهی‌ها",
        ),
    },
    PLAN_SILVER: {
        "key": PLAN_SILVER,
        "title": "نقره‌ای",
        "price": 450_000,
        "price_label": "۴۵۰ هزار تومان",
        "rank": 2,
        "days": 15,
        "show_on_home": False,
        "features": (
            "۱۵ روز نردبان در قسمت نقره‌ای آگهی‌ها",
        ),
    },
    PLAN_GOLD: {
        "key": PLAN_GOLD,
        "title": "طلایی",
        "price": 800_000,
        "price_label": "۸۰۰ هزار تومان",
        "rank": 3,
        "days": 30,
        "show_on_home": True,
        "features": (
            "یک ماه نردبان آگهی کلاب",
            "نمایش در آگهی طلایی صفحه اصلی",
        ),
    },
}


def venue_plan_or_none(value):
    if value in VENUE_PLANS:
        return value
    return None
