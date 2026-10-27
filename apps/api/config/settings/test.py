import os

from .base import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ.get("TEST_DATABASE_NAME", ":memory:")}}
