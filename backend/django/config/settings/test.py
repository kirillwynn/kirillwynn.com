from config.settings.base import *  # noqa: F403

SECRET_KEY = "test-only"
ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:3000"]
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"

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
SUBSCRIPTION_SIGNING_SECRET = "test-subscription-signing-secret-32-bytes"
EMAIL_PROVIDER_ADAPTER = "apps.subscriptions.providers.memory.MemoryEmailProvider"
RESEND_WEBHOOK_SECRET = "whsec_dGVzdC13ZWJob29rLXNlY3JldC0zMi1ieXRlcy0wMQ=="

SOCIALACCOUNT_PROVIDERS = {
    **SOCIALACCOUNT_PROVIDERS,  # noqa: F405
    "google": {
        **SOCIALACCOUNT_PROVIDERS["google"],  # noqa: F405
        "APPS": [
            {
                "name": "Google OAuth test",
                "client_id": "google-test-client-id",
                "secret": "google-test-client-secret",
                "key": "",
            }
        ],
    },
    "github": {
        **SOCIALACCOUNT_PROVIDERS["github"],  # noqa: F405
        "APPS": [
            {
                "name": "GitHub OAuth test",
                "client_id": "github-test-client-id",
                "secret": "github-test-client-secret",
                "key": "",
            }
        ],
    },
}
