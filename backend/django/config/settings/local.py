from config.settings.base import *  # noqa: F403

DEBUG = True
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only")  # noqa: F405
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list(  # noqa: F405
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost:3000,http://localhost:8000",
)
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
