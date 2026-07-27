from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured

TOKEN_SCHEMA_VERSION = 1
TOKEN_SALT = "subscriptions.credentials.v1"


class InvalidSubscriptionCredential(Exception):
    pass


@dataclass(frozen=True)
class SubscriptionCredential:
    subscriber_id: str
    purpose: str
    token_version: int


def _signing_secret():
    secret = settings.SUBSCRIPTION_SIGNING_SECRET
    if len(secret.encode()) < 32:
        raise ImproperlyConfigured("SUBSCRIPTION_SIGNING_SECRET must be at least 32 bytes")
    return secret


class ImmutableTimestampSigner(signing.TimestampSigner):
    def __init__(self, *, issued_at, **kwargs):
        super().__init__(**kwargs)
        self.issued_at = issued_at

    def timestamp(self):
        return signing.b62_encode(int(self.issued_at.timestamp()))


def issue_credential(*, subscriber, purpose, token_version, issued_at=None):
    signer = (
        ImmutableTimestampSigner(
            issued_at=issued_at,
            key=_signing_secret(),
            salt=TOKEN_SALT,
        )
        if isinstance(issued_at, datetime)
        else signing.TimestampSigner(key=_signing_secret(), salt=TOKEN_SALT)
    )
    return signer.sign_object(
        {
            "v": TOKEN_SCHEMA_VERSION,
            "purpose": purpose,
            "subscriber_id": str(subscriber.pk),
            "token_version": token_version,
        },
        compress=False,
    )


def read_credential(credential, *, purpose):
    if not isinstance(credential, str) or not credential or len(credential) > 2_048:
        raise InvalidSubscriptionCredential
    max_age = settings.SUBSCRIPTION_TOKEN_TTL_SECONDS if purpose == "confirm" else None
    try:
        payload = signing.loads(
            credential,
            key=_signing_secret(),
            salt=TOKEN_SALT,
            max_age=max_age,
        )
    except (signing.BadSignature, ValueError, TypeError):
        raise InvalidSubscriptionCredential from None
    if (
        not isinstance(payload, dict)
        or payload.get("v") != TOKEN_SCHEMA_VERSION
        or payload.get("purpose") != purpose
        or not isinstance(payload.get("subscriber_id"), str)
        or not isinstance(payload.get("token_version"), int)
        or payload["token_version"] < 1
    ):
        raise InvalidSubscriptionCredential
    return SubscriptionCredential(
        subscriber_id=payload["subscriber_id"],
        purpose=purpose,
        token_version=payload["token_version"],
    )
