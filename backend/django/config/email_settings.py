import re
from email.utils import parseaddr

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email

MAX_EMAIL_FROM_ADDRESS_LENGTH = 512
MAX_TRANSPORT_IDENTITY_LENGTH = 128
TRANSPORT_IDENTITY_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._:/-]{0,127})$")


def normalize_email_from_address(value, *, setting_name="EMAIL_FROM_ADDRESS"):
    if not isinstance(value, str):
        raise ImproperlyConfigured(f"{setting_name} must be a valid mailbox")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > MAX_EMAIL_FROM_ADDRESS_LENGTH
        or "\r" in normalized
        or "\n" in normalized
    ):
        raise ImproperlyConfigured(f"{setting_name} must be a valid mailbox")
    _, mailbox = parseaddr(normalized, strict=True)
    try:
        validate_email(mailbox)
    except ValidationError as error:
        raise ImproperlyConfigured(f"{setting_name} must be a valid mailbox") from error
    return normalized


def normalize_transport_identity(value, *, name):
    if not isinstance(value, str):
        raise ImproperlyConfigured(f"{name} must be a normalized transport identifier")
    normalized = value.strip().lower()
    if not TRANSPORT_IDENTITY_PATTERN.fullmatch(normalized):
        raise ImproperlyConfigured(f"{name} must be a normalized transport identifier")
    return normalized
