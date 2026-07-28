import base64
import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import URLValidator
from svix.webhooks import Webhook

from config.email_settings import normalize_email_from_address, normalize_transport_identity
from config.settings.base import *  # noqa: F403

SERVICE_ROLE = os.environ.get("SERVICE_ROLE", "web").strip()
if SERVICE_ROLE not in {"web", "worker"}:
    raise ImproperlyConfigured("SERVICE_ROLE must be 'web' or 'worker'")

required_environment = {
    "DJANGO_SECRET_KEY": SECRET_KEY,  # noqa: F405
    "POSTGRES_HOST": os.environ.get("POSTGRES_HOST"),
    "POSTGRES_DB": os.environ.get("POSTGRES_DB"),
    "POSTGRES_USER": os.environ.get("POSTGRES_USER"),
    "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
    "PUBLIC_SITE_URL": os.environ.get("PUBLIC_SITE_URL"),
    "REVALIDATION_URL": os.environ.get("REVALIDATION_URL"),
    "REVALIDATION_SECRET": os.environ.get("REVALIDATION_SECRET"),
    "EMAIL_FROM_ADDRESS": os.environ.get("EMAIL_FROM_ADDRESS"),
    "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE": os.environ.get("EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE"),
    "SUBSCRIPTION_SIGNING_SECRET": os.environ.get("SUBSCRIPTION_SIGNING_SECRET"),
    "S3_MEDIA_ACCESS_KEY_ID": os.environ.get("S3_MEDIA_ACCESS_KEY_ID"),
    "S3_MEDIA_SECRET_ACCESS_KEY": os.environ.get("S3_MEDIA_SECRET_ACCESS_KEY"),
    "S3_MEDIA_BUCKET": os.environ.get("S3_MEDIA_BUCKET"),
    "S3_MEDIA_PREFIX": os.environ.get("S3_MEDIA_PREFIX"),
    "S3_MEDIA_ENDPOINT_URL": os.environ.get("S3_MEDIA_ENDPOINT_URL"),
    "S3_MEDIA_REGION": os.environ.get("S3_MEDIA_REGION"),
    "S3_MEDIA_ADDRESSING_STYLE": os.environ.get("S3_MEDIA_ADDRESSING_STYLE"),
    "S3_MEDIA_PUBLIC_ORIGIN": os.environ.get("S3_MEDIA_PUBLIC_ORIGIN"),
}
if SERVICE_ROLE == "web":
    required_environment.update(
        {
            "DJANGO_ALLOWED_HOSTS": os.environ.get("DJANGO_ALLOWED_HOSTS"),
            "DJANGO_CSRF_TRUSTED_ORIGINS": os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS"),
            "WAGTAIL_ADMIN_BASE_URL": os.environ.get("WAGTAIL_ADMIN_BASE_URL"),
            "FRONTEND_PREVIEW_URL": os.environ.get("FRONTEND_PREVIEW_URL"),
            **OAUTH_CREDENTIALS,  # noqa: F405
        }
    )
EMAIL_PROVIDER_ADAPTER = os.environ.get(
    "EMAIL_PROVIDER_ADAPTER",
    "apps.subscriptions.providers.resend.ResendEmailProvider",
).strip()
if EMAIL_PROVIDER_ADAPTER == "apps.subscriptions.providers.resend.ResendEmailProvider":
    resend_required = (
        {"RESEND_API_KEY": os.environ.get("RESEND_API_KEY")}
        if SERVICE_ROLE == "worker"
        else {"RESEND_WEBHOOK_SECRET": os.environ.get("RESEND_WEBHOOK_SECRET")}
    )
    required_environment.update(resend_required)
missing_environment = [
    name
    for name, value in required_environment.items()
    if not value or (isinstance(value, str) and not value.strip())
]
if missing_environment:
    missing_names = ", ".join(sorted(missing_environment))
    raise ImproperlyConfigured(
        f"Missing required production environment variables: {missing_names}"
    )


def public_origin(value):
    try:
        URLValidator(schemes=["http", "https"])(value)
    except ValidationError as error:
        raise ImproperlyConfigured("PUBLIC_SITE_URL must be a valid http(s) URL") from error
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ImproperlyConfigured(
            "PUBLIC_SITE_URL must be an http(s) origin without path, query, or fragment"
        )
    try:
        parsed.port
    except ValueError as error:
        raise ImproperlyConfigured("PUBLIC_SITE_URL has an invalid port") from error
    return value.rstrip("/")


def media_prefix(value):
    normalized = value.strip().strip("/")
    if not normalized or normalized in {".", ".."}:
        raise ImproperlyConfigured("S3_MEDIA_PREFIX must be a non-empty object prefix")
    if any(segment in {"", ".", ".."} for segment in normalized.split("/")):
        raise ImproperlyConfigured("S3_MEDIA_PREFIX contains an unsafe path segment")
    return normalized


if len(os.environ["REVALIDATION_SECRET"].encode()) < 32:
    raise ImproperlyConfigured("REVALIDATION_SECRET must be at least 32 bytes")
if len(os.environ["SUBSCRIPTION_SIGNING_SECRET"].encode()) < 32:
    raise ImproperlyConfigured("SUBSCRIPTION_SIGNING_SECRET must be at least 32 bytes")
EMAIL_FROM_ADDRESS = normalize_email_from_address(os.environ["EMAIL_FROM_ADDRESS"])
EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE = normalize_transport_identity(
    os.environ["EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE"],
    name="EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE",
)
if (
    SERVICE_ROLE == "web"
    and EMAIL_PROVIDER_ADAPTER == "apps.subscriptions.providers.resend.ResendEmailProvider"
):
    try:
        webhook_secret = os.environ["RESEND_WEBHOOK_SECRET"].strip()
        if not webhook_secret.startswith("whsec_"):
            raise ValueError
        encoded_secret = webhook_secret.removeprefix("whsec_")
        decoded_secret = base64.b64decode(
            encoded_secret + ("=" * (-len(encoded_secret) % 4)),
            validate=True,
        )
        if len(decoded_secret) < 16:
            raise ValueError
        Webhook(webhook_secret)
    except Exception as error:
        raise ImproperlyConfigured(
            "RESEND_WEBHOOK_SECRET must be a valid Svix signing secret"
        ) from error

DEBUG = False
MIDDLEWARE = [
    MIDDLEWARE[0],  # noqa: F405
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],  # noqa: F405
]
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "worker.invalid")  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405
WAGTAILADMIN_BASE_URL = os.environ.get(
    "WAGTAIL_ADMIN_BASE_URL", f"{os.environ['PUBLIC_SITE_URL'].rstrip('/')}/cms"
)
PUBLIC_SITE_URL = public_origin(os.environ["PUBLIC_SITE_URL"])
S3_MEDIA_PUBLIC_ORIGIN = public_origin(os.environ["S3_MEDIA_PUBLIC_ORIGIN"])
S3_MEDIA_ENDPOINT_URL = public_origin(os.environ["S3_MEDIA_ENDPOINT_URL"])
S3_MEDIA_PREFIX = media_prefix(os.environ["S3_MEDIA_PREFIX"])
S3_MEDIA_ADDRESSING_STYLE = os.environ["S3_MEDIA_ADDRESSING_STYLE"].strip().lower()
if S3_MEDIA_ADDRESSING_STYLE not in {"path", "virtual"}:
    raise ImproperlyConfigured("S3_MEDIA_ADDRESSING_STYLE must be 'path' or 'virtual'")
FRONTEND_PREVIEW_URL = os.environ.get("FRONTEND_PREVIEW_URL", f"{PUBLIC_SITE_URL}/api/draft")
WAGTAIL_HEADLESS_PREVIEW = {
    **WAGTAIL_HEADLESS_PREVIEW,  # noqa: F405
    "CLIENT_URLS": {"default": FRONTEND_PREVIEW_URL},
}
REVALIDATION_URL = os.environ["REVALIDATION_URL"]
REVALIDATION_SECRET = os.environ["REVALIDATION_SECRET"]
SUBSCRIPTION_SIGNING_SECRET = os.environ["SUBSCRIPTION_SIGNING_SECRET"]
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_WEBHOOK_SECRET = os.environ.get("RESEND_WEBHOOK_SECRET", "").strip()
RESEND_API_URL = os.environ.get("RESEND_API_URL", "https://api.resend.com/emails")
PREVIEW_COOKIE_SECURE = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_NAME = "__Host-sessionid"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_NAME = "__Host-csrftoken"
CSRF_COOKIE_PATH = "/"
CSRF_COOKIE_DOMAIN = None
ALLAUTH_TRUSTED_PROXY_COUNT = 1
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"

# Wagtail's live preview is intentionally rendered in a same-origin iframe.
SILENCED_SYSTEM_CHECKS = ["security.W019"]

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": os.environ["S3_MEDIA_ACCESS_KEY_ID"].strip(),
            "secret_key": os.environ["S3_MEDIA_SECRET_ACCESS_KEY"].strip(),
            "bucket_name": os.environ["S3_MEDIA_BUCKET"].strip(),
            "location": S3_MEDIA_PREFIX,
            "endpoint_url": S3_MEDIA_ENDPOINT_URL,
            "region_name": os.environ["S3_MEDIA_REGION"].strip(),
            "addressing_style": S3_MEDIA_ADDRESSING_STYLE,
            "custom_domain": S3_MEDIA_PUBLIC_ORIGIN.removeprefix("https://").removeprefix(
                "http://"
            ),
            "url_protocol": f"{urlsplit(S3_MEDIA_PUBLIC_ORIGIN).scheme}:",
            "querystring_auth": False,
            "default_acl": None,
            "file_overwrite": False,
            "object_parameters": {
                "CacheControl": "public, max-age=31536000, immutable",
            },
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

WAGTAIL_ENABLE_UPDATE_CHECK = False
WAGTAILDOCS_SERVE_METHOD = "redirect"
STATIC_ROOT = "/opt/kirillwynn/staticfiles"
