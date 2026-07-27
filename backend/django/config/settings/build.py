"""Credential-free settings used only while assembling immutable images."""

from config.settings.test import *  # noqa: F403

DEBUG = False
SECRET_KEY = "image-build-only-not-a-runtime-secret"
STATIC_ROOT = os.environ.get("STATIC_ROOT", "/opt/kirillwynn/staticfiles")  # noqa: F405
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
