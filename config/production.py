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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
