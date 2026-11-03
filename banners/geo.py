import hashlib
import hmac
import math
import random
from urllib.parse import quote
from uuid import uuid4

from django.conf import settings

IRAN_CITIES = [
    "تهران",
    "کرج",
    "اصفهان",
    "مشهد",
    "شیراز",
    "تبریز",
    "اهواز",
    "قم",
    "کرمانشاه",
    "رشت",
    "ساری",
    "ارومیه",
    "یزد",
    "کرمان",
    "همدان",
    "بندرعباس",
    "زاهدان",
    "اردبیل",
    "قزوین",
    "زنجان",
    "گرگان",
    "بوشهر",
    "خرم‌آباد",
    "سنندج",
    "ایلام",
    "شهرکرد",
    "یاسوج",
    "بجنورد",
    "بیرجند",
    "سمنان",
    "اراک",
    "کاشان",
    "کیش",
    "قشم",
    "نیشابور",
]

CITY_SESSION_KEY = "places_city"
GUEST_RATING_KEY = "places_guest_key"
CAPTCHA_SESSION_KEY = "venue_comment_captcha"


def haversine_km(lat1, lng1, lat2, lng2):
    try:
        lat1 = float(lat1)
        lng1 = float(lng1)
        lat2 = float(lat2)
        lng2 = float(lng2)
    except (TypeError, ValueError):
        return None
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    angle = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(min(1.0, angle)))


def format_distance(km):
    if km is None:
        return ""
    if km < 1:
        return f"{int(round(km * 1000))} متر"
    if abs(km - round(km)) < 0.05:
        return f"{int(round(km))} کیلومتر"
    return f"{km:.1f} کیلومتر"


def parse_coord(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if -90 <= number <= 90 or -180 <= number <= 180:
        return number
    return None


def ensure_guest_key(request):
    key = request.session.get(GUEST_RATING_KEY)
    if not key:
        key = uuid4().hex
        request.session[GUEST_RATING_KEY] = key
        request.session.modified = True
    return key


def issue_sum_captcha(request):
    left = random.randint(1, 9)
    right = random.randint(1, 9)
    digest = hmac.new(settings.SECRET_KEY.encode(), f"{left}+{right}={left + right}".encode(), hashlib.sha256).hexdigest()
    request.session[CAPTCHA_SESSION_KEY] = {"left": left, "right": right, "digest": digest}
    request.session.modified = True
    return left, right


def captcha_prompt(request):
    payload = request.session.get(CAPTCHA_SESSION_KEY) or {}
    left = payload.get("left")
    right = payload.get("right")
    if not isinstance(left, int) or not isinstance(right, int):
        return issue_sum_captcha(request)
    return left, right


def captcha_is_valid(request, answer):
    payload = request.session.get(CAPTCHA_SESSION_KEY) or {}
    left = payload.get("left")
    right = payload.get("right")
    digest = payload.get("digest") or ""
    try:
        number = int(str(answer).strip())
    except (TypeError, ValueError):
        return False
    if not isinstance(left, int) or not isinstance(right, int):
        return False
    expected = hmac.new(settings.SECRET_KEY.encode(), f"{left}+{right}={left + right}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, expected):
        return False
    return number == left + right


def consume_captcha(request):
    request.session.pop(CAPTCHA_SESSION_KEY, None)
    request.session.modified = True


def navigation_links(lat, lng, name):
    query_name = " ".join(str(name or "کافه کلاب").split()) or "کافه کلاب"
    encoded = quote(query_name)
    dest = f"{lat},{lng}"
    return [
        {
            "id": "google",
            "label": "گوگل مپ",
            "url": f"https://www.google.com/maps/dir/?api=1&destination={dest}",
        },
        {
            "id": "waze",
            "label": "ویز",
            "url": f"https://waze.com/ul?ll={dest}&navigate=yes",
        },
        {
            "id": "neshan",
            "label": "نشان",
            "url": f"https://neshan.org/maps/@{lat},{lng},16z,0p/routing/car",
        },
        {
            "id": "balad",
            "label": "بلد",
            "url": f"https://balad.ir/location?latitude={lat}&longitude={lng}",
        },
        {
            "id": "apple",
            "label": "اپل مپ",
            "url": f"https://maps.apple.com/?daddr={dest}&q={encoded}",
            "ios_url": f"maps://?daddr={dest}&q={encoded}",
        },
        {
            "id": "geo",
            "label": "سایر برنامه‌ها",
            "url": f"geo:{dest}?q={dest}({encoded})",
            "ios_url": f"maps://?daddr={dest}&q={encoded}",
        },
    ]
