import math
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.email_settings import normalize_email_from_address

BASE_DIR = Path(__file__).resolve().parents[2]


def env_list(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


def positive_finite_float(name: str, default: str) -> float:
    raw_value = os.environ.get(name, default).strip()
    try:
        value = float(raw_value)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a finite positive number") from None
    if not math.isfinite(value) or value <= 0:
        raise ImproperlyConfigured(f"{name} must be a finite positive number")
    return value


def positive_int(name: str, default: str) -> int:
    raw_value = os.environ.get(name, default).strip()
    try:
        value = int(raw_value)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a positive integer") from None
    if value <= 0:
        raise ImproperlyConfigured(f"{name} must be a positive integer")
    return value


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "apps.core",
    "apps.users",
    "apps.blog",
    "apps.discussions",
    "apps.subscriptions",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.google",
    "wagtail_headless_preview",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
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
    "django.contrib.postgres",
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
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "config.urls"
USE_X_FORWARDED_HOST = True

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
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_ADAPTER = "apps.users.adapters.SiteAccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.users.adapters.SiteSocialAccountAdapter"
SOCIALACCOUNT_ONLY = True
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_REQUESTS_TIMEOUT = positive_finite_float("SOCIALACCOUNT_REQUESTS_TIMEOUT", "5")
ALLAUTH_TRUSTED_PROXY_COUNT = int(os.environ.get("ALLAUTH_TRUSTED_PROXY_COUNT", "0"))

OAUTH_CREDENTIALS = {
    name: os.environ.get(name, "").strip()
    for name in (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GITHUB_OAUTH_CLIENT_ID",
        "GITHUB_OAUTH_CLIENT_SECRET",
    )
}


def social_app(provider: str) -> list[dict[str, str]]:
    prefix = provider.upper()
    client_id = OAUTH_CREDENTIALS[f"{prefix}_OAUTH_CLIENT_ID"]
    secret = OAUTH_CREDENTIALS[f"{prefix}_OAUTH_CLIENT_SECRET"]
    if not client_id or not secret:
        return []
    return [
        {
            "name": f"{provider.title()} OAuth",
            "client_id": client_id,
            "secret": secret,
            "key": "",
        }
    ]


SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": social_app("google"),
        "SCOPE": ["openid", "profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "OAUTH_PKCE_ENABLED": True,
        "EMAIL_AUTHENTICATION": True,
    },
    "github": {
        "APPS": social_app("github"),
        "SCOPE": ["user:email"],
        "EMAIL_AUTHENTICATION": True,
    },
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_PATH = "/"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_PATH = "/"
CSRF_COOKIE_HTTPONLY = True

SITE_OWNER_EMAIL = os.environ.get("SITE_OWNER_EMAIL", "").strip()

COMMENT_CREATE_RATE_LIMIT_COUNT = positive_int("COMMENT_CREATE_RATE_LIMIT_COUNT", "10")
COMMENT_CREATE_RATE_LIMIT_WINDOW_SECONDS = positive_int(
    "COMMENT_CREATE_RATE_LIMIT_WINDOW_SECONDS", "60"
)
COMMENT_MUTATION_RATE_LIMIT_COUNT = positive_int("COMMENT_MUTATION_RATE_LIMIT_COUNT", "30")
COMMENT_MUTATION_RATE_LIMIT_WINDOW_SECONDS = positive_int(
    "COMMENT_MUTATION_RATE_LIMIT_WINDOW_SECONDS", "60"
)
REACTION_TOGGLE_RATE_LIMIT_COUNT = positive_int("REACTION_TOGGLE_RATE_LIMIT_COUNT", "60")
REACTION_TOGGLE_RATE_LIMIT_WINDOW_SECONDS = positive_int(
    "REACTION_TOGGLE_RATE_LIMIT_WINDOW_SECONDS", "60"
)

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
WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
        # A language-neutral configuration keeps exact Russian, English, and
        # mixed-language lexemes searchable without applying the wrong stemmer.
        "SEARCH_CONFIG": "simple",
    }
}
WAGTAILADMIN_BASE_URL = os.environ.get("WAGTAIL_ADMIN_BASE_URL", "http://localhost:8000")
PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "http://localhost:3000").rstrip("/")
FRONTEND_PREVIEW_URL = os.environ.get(
    "FRONTEND_PREVIEW_URL",
    "http://localhost:3000/api/draft",
)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
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

EMAIL_PROVIDER_ADAPTER = os.environ.get(
    "EMAIL_PROVIDER_ADAPTER", "apps.subscriptions.providers.memory.MemoryEmailProvider"
).strip()
EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE = os.environ.get(
    "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE",
    "local/test",
)
EMAIL_FROM_ADDRESS = normalize_email_from_address(
    os.environ.get(
        "EMAIL_FROM_ADDRESS",
        "Kirill Wynn <posts@kirillwynn.com>",
    )
)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_WEBHOOK_SECRET = os.environ.get("RESEND_WEBHOOK_SECRET", "").strip()
RESEND_API_URL = os.environ.get("RESEND_API_URL", "https://api.resend.com/emails")
SUBSCRIPTION_SIGNING_SECRET = os.environ.get(
    "SUBSCRIPTION_SIGNING_SECRET",
    "local-subscription-signing-secret-change-me",
)
SUBSCRIPTION_TOKEN_TTL_SECONDS = positive_int("SUBSCRIPTION_TOKEN_TTL_SECONDS", "172800")
SUBSCRIPTION_CONFIRMATION_COOLDOWN_SECONDS = positive_int(
    "SUBSCRIPTION_CONFIRMATION_COOLDOWN_SECONDS", "900"
)
SUBSCRIPTION_RATE_LIMIT_COUNT = positive_int("SUBSCRIPTION_RATE_LIMIT_COUNT", "5")
SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS = positive_int(
    "SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS", "3600"
)
SUBSCRIPTION_CONFIRM_RATE_LIMIT_COUNT = positive_int("SUBSCRIPTION_CONFIRM_RATE_LIMIT_COUNT", "20")
SUBSCRIPTION_CONFIRM_RATE_LIMIT_WINDOW_SECONDS = positive_int(
    "SUBSCRIPTION_CONFIRM_RATE_LIMIT_WINDOW_SECONDS", "3600"
)
EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS = positive_int(
    "EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS", "300"
)
EMAIL_OUTBOX_MAX_ATTEMPTS = positive_int("EMAIL_OUTBOX_MAX_ATTEMPTS", "8")
EMAIL_OUTBOX_RETRY_BASE_SECONDS = positive_int("EMAIL_OUTBOX_RETRY_BASE_SECONDS", "30")
EMAIL_OUTBOX_RETRY_MAX_SECONDS = positive_int("EMAIL_OUTBOX_RETRY_MAX_SECONDS", "21600")
EMAIL_DELIVERY_BATCH_SIZE = positive_int("EMAIL_DELIVERY_BATCH_SIZE", "100")
EMAIL_PROVIDER_TIMEOUT_SECONDS = positive_finite_float("EMAIL_PROVIDER_TIMEOUT_SECONDS", "10")
EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS = positive_int(
    "EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS", "82800"
)
RESEND_WEBHOOK_MAX_BODY_BYTES = positive_int("RESEND_WEBHOOK_MAX_BODY_BYTES", "262144")
RESEND_WEBHOOK_TIMESTAMP_WINDOW_SECONDS = positive_int(
    "RESEND_WEBHOOK_TIMESTAMP_WINDOW_SECONDS", "300"
)
RESEND_SUCCESS_RESPONSE_MAX_BODY_BYTES = positive_int(
    "RESEND_SUCCESS_RESPONSE_MAX_BODY_BYTES", "65536"
)
RESEND_ERROR_RESPONSE_MAX_BODY_BYTES = positive_int("RESEND_ERROR_RESPONSE_MAX_BODY_BYTES", "65536")
EMAIL_WEBHOOK_CORRELATION_TTL_SECONDS = positive_int(
    "EMAIL_WEBHOOK_CORRELATION_TTL_SECONDS", "604800"
)
EMAIL_WEBHOOK_RETENTION_SECONDS = positive_int("EMAIL_WEBHOOK_RETENTION_SECONDS", "2592000")
EMAIL_WEBHOOK_RECONCILIATION_BATCH_SIZE = positive_int(
    "EMAIL_WEBHOOK_RECONCILIATION_BATCH_SIZE", "100"
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
