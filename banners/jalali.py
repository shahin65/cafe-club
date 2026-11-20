from datetime import datetime, timedelta

from django.utils import timezone

WEEKDAYS = (
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنجشنبه",
    "جمعه",
    "شنبه",
    "یکشنبه",
)

JALALI_MONTHS = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

HOUR_CHOICES = [f"{hour:02d}:00" for hour in range(24)]


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def format_jalali_weekday(value):
    if not value:
        return ""
    local = timezone.localtime(value)
    return WEEKDAYS[local.weekday()]


def format_jalali_date(value):
    if not value:
        return ""
    local = timezone.localtime(value)
    year, month, day = gregorian_to_jalali(local.year, local.month, local.day)
    return f"{day} {JALALI_MONTHS[month - 1]} {year}"


def format_jalali_time(value):
    if not value:
        return ""
    local = timezone.localtime(value)
    return f"{local:%H:%M}"


def format_jalali_datetime(value):
    if not value:
        return ""
    date_text = format_jalali_date(value)
    time_text = format_jalali_time(value)
    if date_text and time_text:
        return f"{date_text} — {time_text}"
    return date_text or time_text


def free_ad_date_choices(now=None):
    local = timezone.localtime(now or timezone.now())
    choices = []
    for offset in range(3):
        day = (local + timedelta(days=offset)).date()
        year, month, number = gregorian_to_jalali(day.year, day.month, day.day)
        choices.append(
            {
                "value": day.isoformat(),
                "label": f"{number} {JALALI_MONTHS[month - 1]} {year}",
            }
        )
    return choices


def parse_event_at(date_value, hour_value, now=None, extra_dates=None):
    local_now = timezone.localtime(now or timezone.now())
    date_text = (date_value or "").strip()
    hour_text = (hour_value or "").strip()
    if hour_text not in HOUR_CHOICES:
        raise ValueError("ساعت برگزاری را انتخاب کنید.")
    allowed = {item["value"] for item in free_ad_date_choices(local_now)}
    allowed.update(extra_dates or ())
    if date_text not in allowed:
        raise ValueError("تاریخ ایونت فقط می‌تواند یکی از سه روز آینده باشد.")
    hour, minute = [int(part) for part in hour_text.split(":")]
    year, month, day = [int(part) for part in date_text.split("-")]
    naive = datetime(year, month, day, hour, minute)
    event_at = timezone.make_aware(naive, timezone.get_current_timezone())
    if event_at <= local_now:
        raise ValueError("زمان برگزاری باید در آینده باشد.")
    return event_at
