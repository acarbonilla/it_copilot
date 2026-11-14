import os

from .base import *  # noqa: F403

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes", "on"}
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ.get("TEST_DATABASE_NAME", ":memory:")}}
VAULT_GRANT_PEPPER = os.environ.get("VAULT_GRANT_PEPPER", "test-only-vault-grant-pepper-with-32-bytes-minimum")
