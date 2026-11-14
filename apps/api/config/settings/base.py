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
    "security_audit",
    "documents",
    "copilot",
    "vault",
    "health",
    "session_auth",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "documents.middleware.DocumentUploadSizeMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
USE_TZ = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

INVITATION_TOKEN_TTL_HOURS = 24
INVITATION_DELIVERY_MODE = os.environ.get("INVITATION_DELIVERY_MODE", "disabled")
INVITATION_MAILBOX_ROOT = Path(os.environ.get("INVITATION_MAILBOX_ROOT", REPOSITORY_DIR / "tmp" / "invitations"))
INVITATION_ACTIVATION_BASE_URL = os.environ.get("INVITATION_ACTIVATION_BASE_URL", "http://localhost:3000/activate")

DOCUMENT_MAX_FILE_BYTES = 10 * 1024 * 1024
DOCUMENT_MAX_REQUEST_BYTES = 12 * 1024 * 1024
DOCUMENT_MAX_PDF_PAGES = 500
DOCUMENT_PDF_PREFLIGHT_TIMEOUT_SECONDS = 120
DOCUMENT_PDF_PREFLIGHT_MEMORY_BYTES = 512 * 1024 * 1024
DOCUMENT_EXTRACTION_TIMEOUT_SECONDS = 120
DOCUMENT_EXTRACTION_MEMORY_BYTES = 512 * 1024 * 1024
DOCUMENT_EXTRACTION_MAX_CHARACTERS = 2_000_000
DOCUMENT_JOB_LEASE_SECONDS = 60
DOCUMENT_JOB_HEARTBEAT_SECONDS = 20
DOCUMENT_PRIVATE_STORAGE_ROOT = Path(
    os.environ.get("DOCUMENT_PRIVATE_STORAGE_ROOT", REPOSITORY_DIR / "tmp" / "documents-private")
)

COPILOT_CHUNK_MAX_TOKENS = 600
COPILOT_CHUNK_OVERLAP_TOKENS = 80
COPILOT_INDEX_JOB_LEASE_SECONDS = 60
COPILOT_INDEX_CANDIDATE_LIMIT = 40
COPILOT_EVIDENCE_CHUNK_LIMIT = 8
COPILOT_EVIDENCE_PER_DOCUMENT_LIMIT = 3
COPILOT_EVIDENCE_TOKEN_LIMIT = 12_000
COPILOT_QUESTION_MAX_CHARACTERS = 2_000
COPILOT_PROVIDER_ENABLED = False
COPILOT_PRIVATE_TRANSFER_AUTHORIZED = False
COPILOT_PROVIDER_MODEL = "gpt-5-mini"
COPILOT_PROVIDER_MODEL_ALLOWLIST = ("gpt-5-mini",)
COPILOT_PROVIDER_TIMEOUT_SECONDS = 30
COPILOT_PROVIDER_MAX_RESPONSE_CHARACTERS = 8_000
COPILOT_CONVERSATION_MAX_MESSAGES = 100
COPILOT_CONVERSATION_PAGE_SIZE_MAX = 100
COPILOT_CONVERSATION_RETENTION_DAYS = 30

VAULT_KEK_FILE = os.environ.get("VAULT_KEK_FILE", "")
VAULT_GRANT_PEPPER = os.environ.get("VAULT_GRANT_PEPPER", "")
VAULT_MAINTENANCE_OPERATORS_FILE = os.environ.get("VAULT_MAINTENANCE_OPERATORS_FILE", "")
VAULT_MAINTENANCE_AUTH_KEY_FILE = os.environ.get("VAULT_MAINTENANCE_AUTH_KEY_FILE", "")
VAULT_BACKUP_MANIFEST_ROOT = os.environ.get("VAULT_BACKUP_MANIFEST_ROOT", "")
VAULT_BACKUP_BUNDLE_ROOT = os.environ.get("VAULT_BACKUP_BUNDLE_ROOT", "")
VAULT_MANIFEST_AUTH_KEY_FILE = os.environ.get("VAULT_MANIFEST_AUTH_KEY_FILE", "")
VAULT_BUNDLE_PROTECTION_KEY_FILE = os.environ.get("VAULT_BUNDLE_PROTECTION_KEY_FILE", "")

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

COOKIE_SECURE = os.environ.get("DJANGO_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_SECURE = COOKIE_SECURE
CSRF_COOKIE_SECURE = COOKIE_SECURE

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
CORS_ALLOWED_ORIGINS = [FRONTEND_ORIGIN]
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"
CSRF_TRUSTED_ORIGINS = [FRONTEND_ORIGIN, "http://localhost:8000", "http://localhost:8100"]
CSRF_FAILURE_VIEW = "config.errors.csrf_failure"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "config.errors.structured_exception_handler",
}
