"""WSGI entry point for cPanel's Python application selector."""

import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.production"

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
