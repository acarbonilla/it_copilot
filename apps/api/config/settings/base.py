import os
from pathlib import Path

from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_DIR = API_DIR.parents[1]
load_dotenv(REPOSITORY_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-development-only-key")
DEBUG = False
ALLOWED_HOSTS = [value.strip() for value in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if value.strip()]

# The custom user model is configured before auth migrations are enabled.
# Admin and sessions remain out of scope until their owning tasks.
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "corsheaders",
    "rest_framework",
    "accounts",
    "health",
    "session_auth",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
USE_TZ = True

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

COOKIE_SECURE = os.environ.get("DJANGO_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_SECURE = COOKIE_SECURE

CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"
CSRF_TRUSTED_ORIGINS = ["http://localhost:3000", "http://localhost:8000"]
CSRF_FAILURE_VIEW = "config.errors.csrf_failure"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "config.errors.structured_exception_handler",
}
