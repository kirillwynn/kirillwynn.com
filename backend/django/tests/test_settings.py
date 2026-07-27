import os
import subprocess
import sys

import pytest

PRODUCTION_SECRET = "s" * 32
OAUTH_CREDENTIAL_NAMES = (
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GITHUB_OAUTH_CLIENT_ID",
    "GITHUB_OAUTH_CLIENT_SECRET",
)


def production_environment():
    environment = os.environ.copy()
    environment.pop("SOCIALACCOUNT_REQUESTS_TIMEOUT", None)
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
            "EMAIL_PROVIDER_ADAPTER": "apps.subscriptions.providers.resend.ResendEmailProvider",
            "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE": "resend/production/account-main",
            "EMAIL_FROM_ADDRESS": "Kirill Wynn <posts@example.com>",
            "RESEND_API_KEY": "resend-production-check",
            "RESEND_WEBHOOK_SECRET": "whsec_dGVzdC13ZWJob29rLXNlY3JldC0zMi1ieXRlcy0wMQ==",
            "SUBSCRIPTION_SIGNING_SECRET": "subscription-production-secret-check",
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


@pytest.mark.parametrize(
    "missing_name",
    [
        "RESEND_API_KEY",
        "RESEND_WEBHOOK_SECRET",
        "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE",
        "SUBSCRIPTION_SIGNING_SECRET",
    ],
)
def test_production_resend_settings_fail_fast(missing_name):
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


def test_production_rejects_short_subscription_signing_secret():
    environment = production_environment()
    environment["SUBSCRIPTION_SIGNING_SECRET"] = "short"

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert "SUBSCRIPTION_SIGNING_SECRET must be at least 32 bytes" in result.stderr


def test_non_resend_production_adapter_does_not_require_resend_credentials():
    environment = production_environment()
    environment["EMAIL_PROVIDER_ADAPTER"] = (
        "apps.subscriptions.providers.memory.MemoryEmailProvider"
    )
    environment["EMAIL_FROM_ADDRESS"] = "  Memory Sender <memory@example.com>  "
    for name in ("RESEND_API_KEY", "RESEND_WEBHOOK_SECRET"):
        environment.pop(name)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config.settings import production; print(production.EMAIL_FROM_ADDRESS)",
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "Memory Sender <memory@example.com>"


def test_every_production_adapter_requires_provider_independent_from_address():
    environment = production_environment()
    environment["EMAIL_PROVIDER_ADAPTER"] = (
        "apps.subscriptions.providers.memory.MemoryEmailProvider"
    )
    environment.pop("EMAIL_FROM_ADDRESS")

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert "Missing required production environment variables: EMAIL_FROM_ADDRESS" in result.stderr


def test_every_production_adapter_requires_idempotency_namespace():
    environment = production_environment()
    environment["EMAIL_PROVIDER_ADAPTER"] = (
        "apps.subscriptions.providers.memory.MemoryEmailProvider"
    )
    environment.pop("EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE")
    for name in ("RESEND_API_KEY", "RESEND_WEBHOOK_SECRET"):
        environment.pop(name)

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert (
        "Missing required production environment variables: "
        "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE" in result.stderr
    )


def test_production_rejects_whitespace_only_from_address():
    environment = production_environment()
    environment["EMAIL_FROM_ADDRESS"] = " \t "

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert "EMAIL_FROM_ADDRESS must be a valid mailbox" in result.stderr


@pytest.mark.parametrize(
    "value",
    [
        "contains whitespace",
        "contains@symbol",
        "x" * 129,
    ],
)
def test_production_rejects_invalid_provider_idempotency_namespace(value):
    environment = production_environment()
    environment["EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE"] = value

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert (
        "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE must be a normalized transport identifier"
        in result.stderr
    )


def test_production_normalizes_provider_idempotency_namespace():
    environment = production_environment()
    environment["EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE"] = " Resend/Production/Account-Main "

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from config.settings import production; "
                "print(production.EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE)"
            ),
        ],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.stdout.strip() == "resend/production/account-main"


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        (
            "EMAIL_FROM_ADDRESS",
            "not-an-email",
            "EMAIL_FROM_ADDRESS must be a valid mailbox",
        ),
        (
            "EMAIL_FROM_ADDRESS",
            "Posts <posts@example.com>\r\nBcc: target@example.com",
            "EMAIL_FROM_ADDRESS must be a valid mailbox",
        ),
        (
            "EMAIL_FROM_ADDRESS",
            f"{'x' * 500} <posts@example.com>",
            "EMAIL_FROM_ADDRESS must be a valid mailbox",
        ),
        (
            "RESEND_WEBHOOK_SECRET",
            "not-a-svix-secret",
            "RESEND_WEBHOOK_SECRET must be a valid Svix signing secret",
        ),
    ],
)
def test_production_rejects_malformed_resend_configuration(name, value, message):
    environment = production_environment()
    environment[name] = value

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert message in result.stderr


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
    "credential_name",
    OAUTH_CREDENTIAL_NAMES,
)
@pytest.mark.parametrize("missing_value", [None, "", " ", "\t", "\n"])
def test_production_settings_reject_missing_or_blank_oauth_credentials(
    credential_name,
    missing_value,
):
    environment = production_environment()
    if missing_value is None:
        environment.pop(credential_name)
    else:
        environment[credential_name] = missing_value

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert result.stderr.rstrip().endswith(
        "django.core.exceptions.ImproperlyConfigured: "
        f"Missing required production environment variables: {credential_name}"
    )
    for value in production_environment().values():
        if "production-check" in value or "production-secret-check" in value:
            assert value not in result.stdout
            assert value not in result.stderr


def test_production_settings_strip_oauth_credentials_and_build_both_apps():
    environment = production_environment()
    for name in OAUTH_CREDENTIAL_NAMES:
        environment[name] = f" \t{environment[name]}\n"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from config.settings import production as s; "
                "assert s.SOCIALACCOUNT_PROVIDERS['google']['APPS']; "
                "assert s.SOCIALACCOUNT_PROVIDERS['github']['APPS']; "
                "assert all(value == value.strip() for value in s.OAUTH_CREDENTIALS.values())"
            ),
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "\t",
        "\n",
        "0",
        "-1",
        "nan",
        "NaN",
        "inf",
        "-inf",
        "infinity",
        "sensitive-invalid-timeout",
    ],
)
def test_production_settings_reject_invalid_socialaccount_timeout(value):
    environment = production_environment()
    environment["SOCIALACCOUNT_REQUESTS_TIMEOUT"] = value

    result = subprocess.run(
        [sys.executable, "-c", "from config.settings import production"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    assert result.stderr.rstrip().endswith(
        "django.core.exceptions.ImproperlyConfigured: "
        "SOCIALACCOUNT_REQUESTS_TIMEOUT must be a finite positive number"
    )
    assert "sensitive-invalid-timeout" not in result.stderr
    for credential_name in OAUTH_CREDENTIAL_NAMES:
        assert environment[credential_name] not in result.stdout
        assert environment[credential_name] not in result.stderr


def test_production_settings_accept_positive_finite_socialaccount_timeout():
    environment = production_environment()
    environment["SOCIALACCOUNT_REQUESTS_TIMEOUT"] = " \t2.75\n"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from config.settings import production as s; "
                "assert s.SOCIALACCOUNT_REQUESTS_TIMEOUT == 2.75"
            ),
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == ""


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
