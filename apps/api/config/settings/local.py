import os

from .base import *  # noqa: F403

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
            "connect_timeout": int(os.environ.get("MYSQL_CONNECT_TIMEOUT", "5")),
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
