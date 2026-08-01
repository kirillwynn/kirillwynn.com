from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.users.identity import normalize_email_address
from apps.users.models import AuthCredential, User

_CREDENTIAL_RE = re.compile(r"^v1\.([0-9a-f]{32})\.([0-9]{10})\.([A-Za-z0-9_-]{43})$")
MAX_CREDENTIAL_LENGTH = 160


class CredentialError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ParsedCredential:
    credential_id: uuid.UUID
    expires_at: int


def _signing_key(purpose: str) -> bytes:
    value = settings.AUTH_CREDENTIAL_SIGNING_SECRET
    if not isinstance(value, str) or len(value.encode()) < 32:
        raise RuntimeError("Auth credential signing is not configured")
    if purpose not in AuthCredential.Purpose.values:
        raise RuntimeError("Unsupported auth credential purpose")
    return hmac.new(
        value.encode(),
        f"stage17-auth-credential-key-v1|{purpose}".encode(),
        hashlib.sha256,
    ).digest()


def _payload(record: AuthCredential, expires_at: int) -> bytes:
    return "|".join(
        (
            "stage17-auth-v1",
            record.purpose,
            record.pk.hex,
            str(record.user_id),
            record.email_normalized,
            str(record.auth_state_version),
            str(expires_at),
        )
    ).encode()


def issue_credential(record: AuthCredential) -> str:
    expires_at = int(record.expires_at.astimezone(UTC).timestamp())
    digest = hmac.new(
        _signing_key(record.purpose),
        _payload(record, expires_at),
        hashlib.sha256,
    ).digest()
    tag = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return f"v1.{record.pk.hex}.{expires_at}.{tag}"


def credential_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def parse_credential(value) -> ParsedCredential:
    if not isinstance(value, str) or not value or len(value) > MAX_CREDENTIAL_LENGTH:
        raise CredentialError("invalid")
    match = _CREDENTIAL_RE.fullmatch(value)
    if not match:
        raise CredentialError("invalid")
    try:
        credential_id = uuid.UUID(hex=match.group(1))
        expires_at = int(match.group(2))
    except (ValueError, OverflowError):
        raise CredentialError("invalid") from None
    return ParsedCredential(credential_id=credential_id, expires_at=expires_at)


def new_credential(*, user: User, purpose: str, ttl: timedelta, at=None):
    now = at or timezone.now()
    record = AuthCredential(
        id=uuid.uuid4(),
        user=user,
        purpose=purpose,
        email_normalized=user.email_normalized,
        auth_state_version=user.auth_state_version,
        expires_at=datetime.fromtimestamp(int((now + ttl).timestamp()), tz=UTC),
        credential_digest="pending",
    )
    raw = issue_credential(record)
    record.credential_digest = credential_digest(raw)
    return record, raw


def _locked_record(raw, *, purpose: str, at=None) -> tuple[AuthCredential, User]:
    parsed = parse_credential(raw)
    try:
        candidate_user_id = AuthCredential.objects.values_list("user_id", flat=True).get(
            pk=parsed.credential_id,
            purpose=purpose,
        )
    except AuthCredential.DoesNotExist:
        raise CredentialError("invalid") from None
    try:
        # Every supported security-state mutation locks User before touching
        # credentials. Keep the same order here to avoid a user/credential
        # deadlock, then re-fetch the credential under its own row lock.
        user = User.objects.select_for_update().get(pk=candidate_user_id)
        record = AuthCredential.objects.select_for_update().get(
            pk=parsed.credential_id,
            purpose=purpose,
            user_id=user.pk,
        )
    except (User.DoesNotExist, AuthCredential.DoesNotExist):
        raise CredentialError("invalid") from None
    expected = issue_credential(record)
    if (
        parsed.expires_at != int(record.expires_at.astimezone(UTC).timestamp())
        or not secrets.compare_digest(expected, raw)
        or not secrets.compare_digest(record.credential_digest, credential_digest(raw))
    ):
        raise CredentialError("invalid")
    if record.used_at is not None:
        raise CredentialError("used")
    now = at or timezone.now()
    if now >= record.expires_at:
        raise CredentialError("expired")
    if not user.is_active or user.is_banned:
        raise CredentialError("unavailable")
    if record.revoked_at is not None:
        raise CredentialError("invalid")
    if (
        user.auth_state_version != record.auth_state_version
        or user.email_normalized != record.email_normalized
    ):
        raise CredentialError("invalid")
    return record, user


def _locked_matching_email_addresses(user: User, email_normalized: str):
    matches = []
    for address in EmailAddress.objects.select_for_update().filter(user=user).order_by("pk"):
        try:
            canonical = normalize_email_address(address.email)[1]
        except ValidationError:
            continue
        if canonical == email_normalized:
            matches.append(address)
    return matches


def _has_locked_verified_primary_email(user: User, email_normalized: str) -> bool:
    matches = _locked_matching_email_addresses(user, email_normalized)
    return len(matches) == 1 and matches[0].primary and matches[0].verified


def _revoke_other_credentials(user: User, *, at, exclude_id=None):
    queryset = AuthCredential.objects.filter(
        user=user,
        used_at__isnull=True,
        revoked_at__isnull=True,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    queryset.update(revoked_at=at)


@transaction.atomic
def confirm_email_credential(raw, *, at=None) -> str:
    now = at or timezone.now()
    record, user = _locked_record(
        raw,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        at=now,
    )
    try:
        matches = _locked_matching_email_addresses(user, record.email_normalized)
        if len(matches) > 1:
            raise CredentialError("unavailable")
        address = matches[0] if matches else None
        EmailAddress.objects.filter(user=user, primary=True).exclude(
            pk=address.pk if address else None
        ).update(primary=False)
        if address is None:
            address = EmailAddress.objects.create(
                user=user,
                email=record.email_normalized,
                primary=True,
                verified=True,
            )
        else:
            address.email = record.email_normalized
            address.primary = True
            address.verified = True
            address.save(update_fields=("email", "primary", "verified"))
    except IntegrityError:
        raise CredentialError("unavailable") from None
    record.used_at = now
    record.save(update_fields=("used_at",))
    user.auth_state_version += 1
    user.save(update_fields=("auth_state_version",))
    _revoke_other_credentials(user, at=now, exclude_id=record.pk)
    return "verified"


def validate_password_pair(user: User, password1, password2) -> str:
    if not isinstance(password1, str) or not isinstance(password2, str):
        raise ValidationError({"password": "Enter a valid password."})
    if password1 != password2:
        raise ValidationError({"password_confirmation": "The passwords do not match."})
    try:
        validate_password(password1, user=user)
    except ValidationError as error:
        raise ValidationError({"password": error.messages}) from None
    return password1


def _set_password(locked: User, password: str, *, now, credential=None):
    if credential is not None:
        # Mark the credential used first so the User model's security-state
        # boundary revokes every *other* outstanding credential. The enclosing
        # transaction rolls this write back if the password save fails.
        credential.used_at = now
        credential.save(update_fields=("used_at",))
    locked.set_password(password)
    locked.auth_state_version += 1
    locked.save(update_fields=("password", "auth_state_version"))
    _revoke_other_credentials(
        locked,
        at=now,
        exclude_id=credential.pk if credential is not None else None,
    )
    return locked


@transaction.atomic
def reset_password_with_credential(raw, password1, password2, *, at=None) -> User:
    now = at or timezone.now()
    record, user = _locked_record(
        raw,
        purpose=AuthCredential.Purpose.PASSWORD_RESET,
        at=now,
    )
    if not _has_locked_verified_primary_email(user, record.email_normalized):
        raise CredentialError("invalid")
    password = validate_password_pair(user, password1, password2)
    return _set_password(user, password, now=now, credential=record)


@transaction.atomic
def set_local_password(user: User, password1, password2, *, current_password=None):
    locked = User.objects.select_for_update().get(pk=user.pk)
    if not locked.is_active or locked.is_banned:
        raise PermissionDenied("This account is unavailable.")
    if locked.has_usable_password():
        if not isinstance(current_password, str) or not locked.check_password(current_password):
            raise ValidationError({"current_password": "The current password is invalid."})
    elif current_password is not None:
        raise ValidationError({"current_password": "This account has no current password."})
    password = validate_password_pair(locked, password1, password2)
    return _set_password(locked, password, now=timezone.now())
