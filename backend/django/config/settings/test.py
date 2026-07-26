from config.settings.base import *  # noqa: F403

SECRET_KEY = "test-only"
ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_TEST_DATABASE", ":memory:"),  # noqa: F405
    },
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

FRONTEND_PREVIEW_URL = "http://frontend.test/api/draft"
PREVIEW_TOKEN_TTL_SECONDS = 600
WAGTAIL_HEADLESS_PREVIEW = {
    **WAGTAIL_HEADLESS_PREVIEW,  # noqa: F405
    "CLIENT_URLS": {"default": FRONTEND_PREVIEW_URL},
}
REVALIDATION_URL = ""
REVALIDATION_SECRET = "test-revalidation-secret"
