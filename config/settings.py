import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path):
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            os.environ.setdefault(key, value)


_load_env_file(BASE_DIR / ".env")

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in {"1", "true", "yes"}
STAFF_TEST_MODE = (
    DEBUG
    and "test" not in sys.argv
    and os.environ.get("STAFF_TEST_MODE", "true").lower() in {"1", "true", "yes", "on"}
)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is false.")
    # Public development fallback; never use this key for a deployed site.
    SECRET_KEY = "django-insecure-development-only-change-before-deployment"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
if DEBUG and "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("*")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "banners.apps.BannersConfig",
    "scenarios.apps.ScenariosConfig",
    "assistant.apps.AssistantAppConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.CafeClubNavMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "config.middleware.DropEnglishPrefixMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.BlockedAccountMiddleware",
    "config.middleware.AttachAppSourceMiddleware",
    "config.middleware.MaintenanceModeMiddleware",
    "config.middleware.PersianDigitsMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "scenarios.context_processors.role_deal",
                "scenarios.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]

LANGUAGE_CODE = "fa"
LANGUAGES = [
    ("fa", "فارسی"),
]
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "cafeclub-media")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "https://s3.ir-central1.arvanstorage.ir")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "ir-central1")
AWS_S3_FILE_OVERWRITE = os.environ.get("AWS_S3_FILE_OVERWRITE", "False").lower() in {"1", "true", "yes", "on"}
AWS_QUERYSTRING_AUTH = os.environ.get("AWS_QUERYSTRING_AUTH", "False").lower() in {"1", "true", "yes", "on"}
AWS_S3_SIGNATURE_VERSION = os.environ.get("AWS_S3_SIGNATURE_VERSION", "s3v4")
AWS_S3_ADDRESSING_STYLE = os.environ.get("AWS_S3_ADDRESSING_STYLE", "path")
AWS_DEFAULT_ACL = os.environ.get("AWS_DEFAULT_ACL", "public-read")
AWS_S3_CUSTOM_DOMAIN = os.environ.get(
    "AWS_S3_CUSTOM_DOMAIN",
    f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.arvanstorage.ir",
)
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "public, max-age=31536000, immutable",
}
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "")

_running_tests = "test" in sys.argv or os.environ.get("CAFECLUB_DISABLE_ARVAN", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
try:
    import storages  # noqa: F401
    _has_django_storages = True
except ImportError:
    _has_django_storages = False
ARVAN_MEDIA_ENABLED = (
    bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME)
    and _has_django_storages
    and not _running_tests
)

STORAGES = {
    "default": {
        "BACKEND": (
            "config.custom_storages.ArvanMediaStorage"
            if ARVAN_MEDIA_ENABLED
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "profile"
LOGOUT_REDIRECT_URL = "home"
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "Cafe Club <noreply@localhost>")
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "").rstrip("/")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")
TELEGRAM_API_BASE_URL = (os.environ.get("TELEGRAM_API_BASE_URL", "") or "").rstrip("/")
TELEGRAM_PROXY_SECRET = os.environ.get("TELEGRAM_PROXY_SECRET", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
BALE_BOT_USERNAME = os.environ.get("BALE_BOT_USERNAME", "")
BALE_AUTH_BOT_TOKEN = os.environ.get("BALE_AUTH_BOT_TOKEN", "")
BALE_WEBHOOK_SECRET = os.environ.get("BALE_WEBHOOK_SECRET", "")
BALE_WEBHOOK_URL = os.environ.get("BALE_WEBHOOK_URL", "")
GAPGPT_API_KEY = os.environ.get("GAPGPT_API_KEY", "")
GAPGPT_BASE_URL = os.environ.get("GAPGPT_BASE_URL", "")
GAPGPT_MODEL = os.environ.get("GAPGPT_MODEL", "")
BALE_BOT_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")
BALE_ADMIN_CHAT_ID = os.environ.get("BALE_ADMIN_CHAT_ID", "")
BITPAY_API_KEY = os.environ.get("BITPAY_API_KEY", "")
BITPAY_SANDBOX = os.environ.get("BITPAY_SANDBOX", "").lower() in {"1", "true", "yes"}
BAZAAR_CLIENT_ID = os.environ.get("BAZAAR_CLIENT_ID", "")
BAZAAR_CLIENT_SECRET = os.environ.get("BAZAAR_CLIENT_SECRET", "")
BAZAAR_REFRESH_TOKEN = os.environ.get("BAZAAR_REFRESH_TOKEN", "")
BAZAAR_REDIRECT_URI = os.environ.get("BAZAAR_REDIRECT_URI", "")
BAZAAR_RSA = os.environ.get("BAZAAR_RSA", "")
MYKET_ACCESS_TOKEN = os.environ.get("MYKET_ACCESS_TOKEN", "")
ANDROID_PACKAGE_NAME = os.environ.get("ANDROID_PACKAGE_NAME", "ir.cafeclub.amytis")
