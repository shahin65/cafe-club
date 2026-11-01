import re

PERSIAN_CHAR = re.compile(r"[\u0600-\u06FF]")
LATIN_LETTER = re.compile(r"[A-Za-z]")
LATIN_RUN = re.compile(r"[A-Za-z]{2,}")

REASON_LINE = "دلیل تصمیم (reason) و متن reply را فقط به فارسی بنویس؛ از انگلیسی استفاده نکن."
FALLBACK_REASON = "این مورد برای بازبینی مدیر ارسال شد."

_PHRASES = (
    (re.compile(r"(?i)needs[_\s-]*human[_\s-]*review"), "نیاز به بازبینی مدیر دارد"),
    (re.compile(r"(?i)needs[_\s-]*review"), "نیاز به بازبینی مدیر دارد"),
    (re.compile(r"(?i)cannot verify (the )?(location|address|venue)( or (the )?(phone|number))?"), "صحت مکان یا شماره تماس قابل راستی‌آزمایی نیست"),
    (re.compile(r"(?i)cannot verify (the )?(phone|number)"), "صحت شماره تماس قابل راستی‌آزمایی نیست"),
    (re.compile(r"(?i)cannot verify (the )?(time|date|schedule)"), "صحت زمان قابل راستی‌آزمایی نیست"),
    (re.compile(r"(?i)(unable to|cannot) verify"), "این اطلاعات قابل راستی‌آزمایی نیست"),
    (re.compile(r"(?i)(unable to|cannot) confirm"), "این مورد قابل تأیید قطعی نیست"),
    (re.compile(r"(?i)incomplete (information|fields|data|details)"), "اطلاعات ناقص است"),
    (re.compile(r"(?i)missing (required )?fields?"), "فیلدهای لازم ناقص است"),
    (re.compile(r"(?i)insufficient (information|evidence|details)"), "اطلاعات کافی نیست"),
    (re.compile(r"(?i)\bspam\b"), "محتوای مشکوک به اسپم"),
    (re.compile(r"(?i)inappropriate"), "محتوای نامناسب"),
    (re.compile(r"(?i)suspicious"), "مشکوک است"),
    (re.compile(r"(?i)\bok\b"), "مورد عادی است"),
)


def looks_latin(text):
    value = text or ""
    latin = len(LATIN_LETTER.findall(value))
    persian = len(PERSIAN_CHAR.findall(value))
    if latin < 8:
        return False
    return latin >= max(persian * 2, 8)


def persian_reason(text, *, fallback=FALLBACK_REASON):
    value = " ".join(str(text or "").split())
    if not value:
        return ""
    if not looks_latin(value):
        return value
    converted = value
    for pattern, fa in _PHRASES:
        converted = pattern.sub(fa, converted)
    converted = " ".join(converted.split())
    if LATIN_RUN.search(converted):
        return fallback
    return converted
