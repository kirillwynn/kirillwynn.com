import os
import subprocess
import sys


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


def test_production_settings_require_wagtail_admin_base_url():
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_SECRET_KEY": "production-check-only",
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "POSTGRES_HOST": "db",
            "POSTGRES_DB": "app",
            "POSTGRES_USER": "app",
            "POSTGRES_PASSWORD": "production-check-only",
        }
    )
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
