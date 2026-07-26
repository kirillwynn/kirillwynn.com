import os
import subprocess
import sys

import pytest

PRODUCTION_SECRET = "s" * 32


def production_environment():
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": "production-check-only",
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            "POSTGRES_HOST": "db",
            "POSTGRES_DB": "app",
            "POSTGRES_USER": "app",
            "POSTGRES_PASSWORD": "production-check-only",
            "WAGTAIL_ADMIN_BASE_URL": "https://example.com/cms",
            "PUBLIC_SITE_URL": "https://example.com/",
            "FRONTEND_PREVIEW_URL": "https://example.com/api/draft",
            "REVALIDATION_URL": "https://example.com/api/revalidate",
            "REVALIDATION_SECRET": PRODUCTION_SECRET,
            "GOOGLE_OAUTH_CLIENT_ID": "google-production-check",
            "GOOGLE_OAUTH_CLIENT_SECRET": "google-production-secret-check",
            "GITHUB_OAUTH_CLIENT_ID": "github-production-check",
            "GITHUB_OAUTH_CLIENT_SECRET": "github-production-secret-check",
        }
    )
    return environment


def test_local_settings_defaults_wagtail_admin_base_url_to_localhost():
    environment = os.environ.copy()
    environment["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
    environment.pop("WAGTAIL_ADMIN_BASE_URL", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.settings import local; print(local.WAGTAILADMIN_BASE_URL)",
        ],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.stdout.strip() == "http://localhost:8000"


def test_local_settings_default_and_normalize_public_site_url():
    environment = os.environ.copy()
    environment["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
    environment.pop("PUBLIC_SITE_URL", None)

    default = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.settings import local; print(local.PUBLIC_SITE_URL)",
        ],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    environment["PUBLIC_SITE_URL"] = "http://localhost:3000/"
    normalized = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.settings import local; print(local.PUBLIC_SITE_URL)",
        ],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert default.stdout.strip() == "http://localhost:3000"
    assert normalized.stdout.strip() == "http://localhost:3000"


def test_production_settings_require_wagtail_admin_base_url():
    environment = production_environment()
    environment.pop("WAGTAIL_ADMIN_BASE_URL", None)

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert (
        "Missing required production environment variables: WAGTAIL_ADMIN_BASE_URL" in result.stderr
    )


@pytest.mark.parametrize(
    "missing_name",
    [
        "PUBLIC_SITE_URL",
        "FRONTEND_PREVIEW_URL",
        "REVALIDATION_URL",
        "REVALIDATION_SECRET",
    ],
)
def test_production_settings_require_preview_and_revalidation_configuration(missing_name):
    environment = production_environment()
    environment.pop(missing_name, None)

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert f"Missing required production environment variables: {missing_name}" in result.stderr


@pytest.mark.parametrize(
    "value",
    [
        "ftp://example.com",
        "https://example.com/posts",
        "https://example.com?query=1",
        "https://example.com#fragment",
        "https://user@example.com",
        "https://example.com:invalid",
        "https://.",
        "example.com",
    ],
)
def test_production_settings_reject_invalid_public_site_origin(value):
    environment = production_environment()
    environment["PUBLIC_SITE_URL"] = value

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert "PUBLIC_SITE_URL" in result.stderr


def test_production_settings_normalize_public_site_origin():
    environment = production_environment()

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.settings import production; print(production.PUBLIC_SITE_URL)",
        ],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.stdout.strip() == "https://example.com"


def test_production_settings_reject_short_revalidation_secret():
    environment = production_environment()
    environment["REVALIDATION_SECRET"] = "short"

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert "REVALIDATION_SECRET must be at least 32 bytes" in result.stderr


def test_headless_preview_settings_use_redirect_and_short_ttl(settings):
    assert settings.WAGTAIL_HEADLESS_PREVIEW == {
        "CLIENT_URLS": {"default": "http://frontend.test/api/draft"},
        "REDIRECT_ON_PREVIEW": True,
        "ENFORCE_TRAILING_SLASH": False,
    }
    assert settings.PREVIEW_TOKEN_TTL_SECONDS == 600


def test_allauth_uses_classic_sessions_minimal_scopes_and_settings_apps(settings):
    assert "allauth.socialaccount" in settings.INSTALLED_APPS
    assert settings.AUTHENTICATION_BACKENDS == [
        "django.contrib.auth.backends.ModelBackend",
        "allauth.account.auth_backends.AuthenticationBackend",
    ]
    assert settings.SOCIALACCOUNT_ONLY is True
    assert settings.SOCIALACCOUNT_LOGIN_ON_GET is False
    assert settings.SOCIALACCOUNT_STORE_TOKENS is False
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"
    assert settings.USE_X_FORWARDED_HOST is True
    assert settings.SOCIALACCOUNT_PROVIDERS["google"]["SCOPE"] == [
        "openid",
        "profile",
        "email",
    ]
    assert settings.SOCIALACCOUNT_PROVIDERS["google"]["AUTH_PARAMS"] == {"access_type": "online"}
    assert settings.SOCIALACCOUNT_PROVIDERS["google"]["OAUTH_PKCE_ENABLED"] is True
    assert settings.SOCIALACCOUNT_PROVIDERS["github"]["SCOPE"] == ["user:email"]
    assert "APP" not in settings.SOCIALACCOUNT_PROVIDERS["google"]
    assert "VERIFIED_EMAIL" not in settings.SOCIALACCOUNT_PROVIDERS["google"]
    assert "VERIFIED_EMAIL" not in settings.SOCIALACCOUNT_PROVIDERS["github"]


@pytest.mark.parametrize(
    "missing_name",
    [
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GITHUB_OAUTH_CLIENT_ID",
        "GITHUB_OAUTH_CLIENT_SECRET",
    ],
)
def test_production_settings_require_every_oauth_credential(missing_name):
    environment = production_environment()
    environment.pop(missing_name)

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert f"Missing required production environment variables: {missing_name}" in result.stderr


def test_production_cookie_and_proxy_hardening():
    environment = production_environment()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from config.settings import production as s; "
                "print(s.SESSION_COOKIE_NAME, s.CSRF_COOKIE_NAME, "
                "s.SESSION_COOKIE_SECURE, s.SESSION_COOKIE_HTTPONLY, "
                "s.CSRF_COOKIE_SECURE, s.CSRF_COOKIE_HTTPONLY, "
                "s.SESSION_COOKIE_SAMESITE, s.ALLAUTH_TRUSTED_PROXY_COUNT)"
            ),
        ],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.stdout.strip() == ("__Host-sessionid __Host-csrftoken True True True True Lax 1")


def test_local_http_uses_standard_cookie_names(settings):
    assert settings.SESSION_COOKIE_NAME == "sessionid"
    assert settings.CSRF_COOKIE_NAME == "csrftoken"
    assert settings.SESSION_COOKIE_SECURE is False
    assert settings.CSRF_COOKIE_SECURE is False
    assert settings.ALLAUTH_TRUSTED_PROXY_COUNT == 0
