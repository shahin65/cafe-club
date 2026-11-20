"""Settings for the isolated Cafe Club hosting application."""

import json
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


config_path = Path(
    os.environ.get("DJANGO_CONFIG_FILE", Path(__file__).resolve().parent.parent / "production.json")
)
try:
    private_config = json.loads(config_path.read_text(encoding="utf-8"))
except FileNotFoundError:
    private_config = {}
except (OSError, ValueError) as exc:
    raise ImproperlyConfigured("Cannot read the production configuration file.") from exc
if not isinstance(private_config, dict):
    raise ImproperlyConfigured("The production configuration must be a JSON object.")

# The shared settings validate this key when DJANGO_DEBUG=false is supplied.
# Load only this value before importing them; explicit environment values win.
if "DJANGO_SECRET_KEY" not in os.environ:
    file_secret = private_config.get("DJANGO_SECRET_KEY")
    if isinstance(file_secret, str):
        os.environ["DJANGO_SECRET_KEY"] = file_secret

from .settings import *  # noqa: E402,F403


def config_value(name, default=None):
    return os.environ.get(name, private_config.get(name, default))


def required_value(name):
    value = config_value(name)
    if not isinstance(value, str) or not value.strip() or value.startswith("REPLACE_WITH_"):
        raise ImproperlyConfigured(f"Set {name} in the production environment or configuration file.")
    return value


DEBUG = False
SECRET_KEY = required_value("DJANGO_SECRET_KEY")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("Use a private random DJANGO_SECRET_KEY of at least 50 characters.")

ALLOWED_HOSTS = [
    host.strip() for host in required_value("DJANGO_ALLOWED_HOSTS").split(",") if host.strip()
]
if not ALLOWED_HOSTS or any("*" in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Configure explicit production hostnames.")
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]

DATABASES = {
    "default": {
        "ENGINE": "mysql.connector.django",
        "NAME": required_value("DB_NAME"),
        "USER": required_value("DB_USER"),
        "PASSWORD": required_value("DB_PASSWORD"),
        "HOST": config_value("DB_HOST", "localhost"),
        "PORT": config_value("DB_PORT", "3306"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
STATIC_ROOT = Path(config_value("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
MEDIA_ROOT = Path(config_value("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_NAME = "cafeclub_sessionid"
CSRF_COOKIE_NAME = "cafeclub_csrftoken"

PUBLIC_SITE_URL = (config_value("PUBLIC_SITE_URL", "") or "").rstrip("/")
TELEGRAM_BOT_TOKEN = config_value("TELEGRAM_BOT_TOKEN", "") or ""
TELEGRAM_BOT_USERNAME = config_value("TELEGRAM_BOT_USERNAME", "") or ""
TELEGRAM_API_BASE_URL = (config_value("TELEGRAM_API_BASE_URL", "") or "").rstrip("/")
TELEGRAM_PROXY_SECRET = config_value("TELEGRAM_PROXY_SECRET", "") or ""
TELEGRAM_WEBHOOK_SECRET = config_value("TELEGRAM_WEBHOOK_SECRET", "") or ""
TELEGRAM_WEBHOOK_URL = config_value("TELEGRAM_WEBHOOK_URL", "") or ""
BALE_BOT_USERNAME = config_value("BALE_BOT_USERNAME", "") or ""
BALE_AUTH_BOT_TOKEN = config_value("BALE_AUTH_BOT_TOKEN", "") or ""
BALE_WEBHOOK_SECRET = config_value("BALE_WEBHOOK_SECRET", "") or ""
BALE_WEBHOOK_URL = config_value("BALE_WEBHOOK_URL", "") or ""
GAPGPT_API_KEY = config_value("GAPGPT_API_KEY", "") or ""
GAPGPT_BASE_URL = config_value("GAPGPT_BASE_URL", "") or ""
GAPGPT_MODEL = config_value("GAPGPT_MODEL", "") or ""
BALE_BOT_TOKEN = config_value("BALE_BOT_TOKEN", "") or ""
BALE_ADMIN_CHAT_ID = str(config_value("BALE_ADMIN_CHAT_ID", "") or "")
BITPAY_API_KEY = config_value("BITPAY_API_KEY", "") or ""
BITPAY_SANDBOX = str(config_value("BITPAY_SANDBOX", "") or "").lower() in {"1", "true", "yes"}
BAZAAR_CLIENT_ID = config_value("BAZAAR_CLIENT_ID", "") or ""
BAZAAR_CLIENT_SECRET = config_value("BAZAAR_CLIENT_SECRET", "") or ""
BAZAAR_REFRESH_TOKEN = config_value("BAZAAR_REFRESH_TOKEN", "") or ""
BAZAAR_REDIRECT_URI = config_value("BAZAAR_REDIRECT_URI", "") or ""
BAZAAR_RSA = config_value("BAZAAR_RSA", "") or ""
MYKET_ACCESS_TOKEN = config_value("MYKET_ACCESS_TOKEN", "") or ""
ANDROID_PACKAGE_NAME = config_value("ANDROID_PACKAGE_NAME", "ir.cafeclub.amytis") or "ir.cafeclub.amytis"

AWS_ACCESS_KEY_ID = config_value("AWS_ACCESS_KEY_ID", AWS_ACCESS_KEY_ID) or ""
AWS_SECRET_ACCESS_KEY = config_value("AWS_SECRET_ACCESS_KEY", AWS_SECRET_ACCESS_KEY) or ""
AWS_STORAGE_BUCKET_NAME = config_value("AWS_STORAGE_BUCKET_NAME", AWS_STORAGE_BUCKET_NAME) or "cafeclub-media"
AWS_S3_ENDPOINT_URL = config_value("AWS_S3_ENDPOINT_URL", AWS_S3_ENDPOINT_URL) or "https://s3.ir-central1.arvanstorage.ir"
AWS_S3_REGION_NAME = config_value("AWS_S3_REGION_NAME", AWS_S3_REGION_NAME) or "ir-central1"
AWS_S3_CUSTOM_DOMAIN = config_value("AWS_S3_CUSTOM_DOMAIN", "") or (
    f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.arvanstorage.ir"
)
FFMPEG_BIN = config_value("FFMPEG_BIN", FFMPEG_BIN) or ""
ARVAN_MEDIA_ENABLED = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME)
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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
