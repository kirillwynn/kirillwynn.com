from dataclasses import dataclass

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


def issue_credential(*, subscriber, purpose, token_version):
    return signing.dumps(
        {
            "v": TOKEN_SCHEMA_VERSION,
            "purpose": purpose,
            "subscriber_id": str(subscriber.pk),
            "token_version": token_version,
        },
        key=_signing_secret(),
        salt=TOKEN_SALT,
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
