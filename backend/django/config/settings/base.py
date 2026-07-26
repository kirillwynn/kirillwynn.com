import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def env_list(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "apps.core",
    "apps.users",
    "apps.blog",
    "wagtail_headless_preview",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.table_block",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "rest_framework",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

database_options = {}
postgres_sslmode = os.environ.get("POSTGRES_SSLMODE", "")
if postgres_sslmode:
    database_options["sslmode"] = postgres_sslmode

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "NAME": os.environ.get("POSTGRES_DB", "kirillwynn"),
        "USER": os.environ.get("POSTGRES_USER", "kirillwynn"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
        "OPTIONS": database_options,
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTH_USER_MODEL = "users.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

WAGTAIL_SITE_NAME = "kirillwynn.com"
WAGTAILADMIN_BASE_URL = os.environ.get("WAGTAIL_ADMIN_BASE_URL", "http://localhost:8000")
PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "http://localhost:3000").rstrip("/")
FRONTEND_PREVIEW_URL = os.environ.get(
    "FRONTEND_PREVIEW_URL",
    "http://localhost:3000/api/draft",
)
PREVIEW_TOKEN_TTL_SECONDS = int(os.environ.get("PREVIEW_TOKEN_TTL_SECONDS", "600"))
PREVIEW_ENTRY_COOKIE_NAME = "kw_preview_credential"
PREVIEW_COOKIE_SECURE = False
WAGTAIL_HEADLESS_PREVIEW = {
    "CLIENT_URLS": {"default": FRONTEND_PREVIEW_URL},
    "REDIRECT_ON_PREVIEW": True,
    "ENFORCE_TRAILING_SLASH": False,
}

REVALIDATION_URL = os.environ.get("REVALIDATION_URL", "")
REVALIDATION_SECRET = os.environ.get("REVALIDATION_SECRET", "")
REVALIDATION_TIMEOUT_SECONDS = float(os.environ.get("REVALIDATION_TIMEOUT_SECONDS", "5"))
REVALIDATION_TIMESTAMP_WINDOW_SECONDS = int(
    os.environ.get("REVALIDATION_TIMESTAMP_WINDOW_SECONDS", "300")
)
REVALIDATION_PROCESSING_TIMEOUT_SECONDS = int(
    os.environ.get("REVALIDATION_PROCESSING_TIMEOUT_SECONDS", "300")
)

# Tags are matched case-insensitively while preserving the first-entered display name.
TAGGIT_CASE_INSENSITIVE = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}
