from email.utils import parseaddr

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email

MAX_EMAIL_FROM_ADDRESS_LENGTH = 512


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
