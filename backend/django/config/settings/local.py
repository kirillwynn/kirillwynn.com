from config.settings.base import *  # noqa: F403

DEBUG = True
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only")  # noqa: F405
AUTH_CREDENTIAL_SIGNING_SECRET = domain_signing_secret(  # noqa: F405
    "AUTH_CREDENTIAL_SIGNING_SECRET",
    "kirillwynn.com/stage17/auth-credential/v1",
    SECRET_KEY,
)
AUTH_RATE_LIMIT_SIGNING_SECRET = domain_signing_secret(  # noqa: F405
    "AUTH_RATE_LIMIT_SIGNING_SECRET",
    "kirillwynn.com/stage17/auth-rate-limit/v1",
    SECRET_KEY,
)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")  # noqa: F405
CSRF_TRUSTED_ORIGINS = env_list(  # noqa: F405
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost:3000,http://localhost:8000",
)
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
