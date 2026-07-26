import os

from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *  # noqa: F403

required_environment = {
    "DJANGO_SECRET_KEY": SECRET_KEY,  # noqa: F405
    "DJANGO_ALLOWED_HOSTS": os.environ.get("DJANGO_ALLOWED_HOSTS"),
    "POSTGRES_HOST": os.environ.get("POSTGRES_HOST"),
    "POSTGRES_DB": os.environ.get("POSTGRES_DB"),
    "POSTGRES_USER": os.environ.get("POSTGRES_USER"),
    "POSTGRES_PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
    "WAGTAIL_ADMIN_BASE_URL": os.environ.get("WAGTAIL_ADMIN_BASE_URL"),
}
missing_environment = [name for name, value in required_environment.items() if not value]
if missing_environment:
    missing_names = ", ".join(sorted(missing_environment))
    raise ImproperlyConfigured(
        f"Missing required production environment variables: {missing_names}"
    )

DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")  # noqa: F405
WAGTAILADMIN_BASE_URL = os.environ["WAGTAIL_ADMIN_BASE_URL"]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
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
