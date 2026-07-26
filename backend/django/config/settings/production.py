import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import URLValidator

from config.settings.base import *  # noqa: F403

required_environment = {
    "DJANGO_SECRET_KEY": SECRET_KEY,  # noqa: F405
    "DJANGO_ALLOWED_HOSTS": os.environ.get("DJANGO_ALLOWED_HOSTS"),
    "DJANGO_CSRF_TRUSTED_ORIGINS": os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS"),
    "POSTGRES_HOST": os.environ.get("POSTGRES_HOST"),
    "POSTGRES_DB": os.environ.get("POSTGRES_DB"),
    "POSTGRES_USER": os.environ.get("POSTGRES_USER"),
    "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
    "WAGTAIL_ADMIN_BASE_URL": os.environ.get("WAGTAIL_ADMIN_BASE_URL"),
    "PUBLIC_SITE_URL": os.environ.get("PUBLIC_SITE_URL"),
    "FRONTEND_PREVIEW_URL": os.environ.get("FRONTEND_PREVIEW_URL"),
    "REVALIDATION_URL": os.environ.get("REVALIDATION_URL"),
    "REVALIDATION_SECRET": os.environ.get("REVALIDATION_SECRET"),
    **OAUTH_CREDENTIALS,  # noqa: F405
}
missing_environment = [name for name, value in required_environment.items() if not value]
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


if len(os.environ["REVALIDATION_SECRET"].encode()) < 32:
    raise ImproperlyConfigured("REVALIDATION_SECRET must be at least 32 bytes")

DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405
WAGTAILADMIN_BASE_URL = os.environ["WAGTAIL_ADMIN_BASE_URL"]
PUBLIC_SITE_URL = public_origin(os.environ["PUBLIC_SITE_URL"])
FRONTEND_PREVIEW_URL = os.environ["FRONTEND_PREVIEW_URL"]
WAGTAIL_HEADLESS_PREVIEW = {
    **WAGTAIL_HEADLESS_PREVIEW,  # noqa: F405
    "CLIENT_URLS": {"default": FRONTEND_PREVIEW_URL},
}
REVALIDATION_URL = os.environ["REVALIDATION_URL"]
REVALIDATION_SECRET = os.environ["REVALIDATION_SECRET"]
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
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

WAGTAIL_ENABLE_UPDATE_CHECK = False
