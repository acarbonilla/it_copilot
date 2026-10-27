import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403


def positive_timeout(name, default="5"):
    try:
        value = int(os.environ.get(name, default))
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ImproperlyConfigured(f"{name} must be a positive integer")
    return value


DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes", "on"}
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DATABASE", "it_support_copilot"),
        "USER": os.environ.get("MYSQL_USER", "it_copilot"),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD", ""),
        "HOST": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "connect_timeout": positive_timeout("MYSQL_CONNECT_TIMEOUT"),
            "read_timeout": positive_timeout("MYSQL_READ_TIMEOUT"),
            "write_timeout": positive_timeout("MYSQL_WRITE_TIMEOUT"),
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
