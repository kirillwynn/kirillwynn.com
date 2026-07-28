"""Test-only settings for the local Django/Next.js Playwright stack."""

from config.settings.test import *  # noqa: F403

PUBLIC_SITE_URL = "http://localhost:3200"
FRONTEND_PREVIEW_URL = "http://localhost:3200/api/draft"
PREVIEW_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = ["http://localhost:3200"]
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

WAGTAIL_HEADLESS_PREVIEW = {
    **WAGTAIL_HEADLESS_PREVIEW,  # noqa: F405
    "CLIENT_URLS": {"default": FRONTEND_PREVIEW_URL},
}

SOCIALACCOUNT_PROVIDERS = {
    **SOCIALACCOUNT_PROVIDERS,  # noqa: F405
    "google": {
        **SOCIALACCOUNT_PROVIDERS["google"],  # noqa: F405
        "ACCESS_TOKEN_URL": "http://127.0.0.1:3202/google/token",
        "AUTHORIZE_URL": "http://127.0.0.1:3202/google/authorize",
        "IDENTITY_URL": "http://127.0.0.1:3202/google/userinfo",
        "FETCH_USERINFO": True,
    },
    "github": {
        **SOCIALACCOUNT_PROVIDERS["github"],  # noqa: F405
        "GITHUB_URL": "http://127.0.0.1:3202/github",
    },
}
