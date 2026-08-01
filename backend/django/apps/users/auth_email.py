from __future__ import annotations

import hashlib
from datetime import timedelta
from urllib.parse import quote

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from apps.subscriptions.providers import configured_email_provider
from apps.subscriptions.providers.base import (
    EmailMessage,
    EmailProviderError,
    PreparedEmailRequest,
    TransportIdentity,
)
from apps.users.credentials import issue_credential, new_credential
from apps.users.identity import normalize_email_address
from apps.users.models import AuthCredential, AuthEmailDelivery, AuthEmailOutbox, User
from config.email_settings import normalize_email_from_address, normalize_transport_identity


def _message_type_for_purpose(purpose):
    if purpose == AuthCredential.Purpose.VERIFY_EMAIL:
        return AuthEmailOutbox.MessageType.EMAIL_VERIFICATION
    if purpose == AuthCredential.Purpose.PASSWORD_RESET:
        return AuthEmailOutbox.MessageType.PASSWORD_RESET
    raise ValueError("Unsupported auth credential purpose")


def _subject(message_type):
    if message_type == AuthEmailOutbox.MessageType.EMAIL_VERIFICATION:
        return "Verify your email address"
    return "Reset your account password"


def _credential_path(message_type):
    if message_type == AuthEmailOutbox.MessageType.EMAIL_VERIFICATION:
        return "/account/verify-email"
    return "/account/password/reset/confirm"


def message_for_auth_delivery(delivery):
    event = delivery.outbox
    if event.message_schema_version != 1:
        raise ValueError("Unsupported immutable auth-email schema")
    credential = issue_credential(event.credential)
    credential_url = (
        f"{event.snapshot_site_url}{_credential_path(event.message_type)}"
        f"#credential={quote(credential, safe='')}"
    )
    context = {"credential_url": credential_url}
    template = (
        "users/email/verification"
        if event.message_type == AuthEmailOutbox.MessageType.EMAIL_VERIFICATION
        else "users/email/password_reset"
    )
    return EmailMessage(
        from_email=event.snapshot_from_email,
        to=event.snapshot_recipient_email,
        subject=event.snapshot_subject,
        text=render_to_string(f"{template}.txt", context),
        html=render_to_string(f"{template}.html", context),
    )


def _prepare(provider, message):
    base = provider.transport_identity()
    namespace = normalize_transport_identity(
        f"{base.idempotency_namespace}/auth",
        name="auth email idempotency namespace",
    )
    return PreparedEmailRequest(
        body=provider.serialize_request(message),
        transport=TransportIdentity(
            contract_id=base.contract_id,
            serializer_version=base.serializer_version,
            idempotency_namespace=namespace,
        ),
    )


def _has_verified_primary_identity(user, *, for_update=False):
    queryset = EmailAddress.objects.filter(user=user, primary=True, verified=True).order_by("pk")
    if for_update:
        queryset = queryset.select_for_update()
    matches = 0
    for address in queryset:
        try:
            canonical = normalize_email_address(address.email)[1]
        except ValidationError:
            continue
        matches += int(canonical == user.email_normalized)
    # Multiple canonical-equivalent rows are an identity invariant failure,
    # not an excuse to select an arbitrary allauth row.
    return matches == 1


@transaction.atomic
def queue_auth_email(*, user: User, purpose: str, at=None, provider=None):
    now = at or timezone.now()
    locked = User.objects.select_for_update().get(pk=user.pk)
    if not locked.email_normalized or not locked.is_active or locked.is_banned:
        return None
    if purpose == AuthCredential.Purpose.PASSWORD_RESET and not _has_verified_primary_identity(
        locked, for_update=True
    ):
        return None
    if purpose == AuthCredential.Purpose.VERIFY_EMAIL and _has_verified_primary_identity(
        locked, for_update=True
    ):
        return None

    AuthCredential.objects.filter(
        user=locked,
        purpose=purpose,
        used_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=now)
    ttl = (
        timedelta(seconds=settings.AUTH_EMAIL_VERIFICATION_TTL_SECONDS)
        if purpose == AuthCredential.Purpose.VERIFY_EMAIL
        else timedelta(seconds=settings.AUTH_PASSWORD_RESET_TTL_SECONDS)
    )
    credential, _ = new_credential(user=locked, purpose=purpose, ttl=ttl, at=now)
    credential.save(force_insert=True)
    message_type = _message_type_for_purpose(purpose)
    event = AuthEmailOutbox.objects.create(
        message_type=message_type,
        credential=credential,
        user=locked,
        snapshot_recipient_email=locked.email_normalized,
        snapshot_from_email=normalize_email_from_address(settings.EMAIL_FROM_ADDRESS),
        snapshot_site_url=settings.PUBLIC_SITE_URL.rstrip("/"),
        snapshot_subject=_subject(message_type),
        available_at=now,
        idempotency_key=f"auth/{message_type}/{credential.pk.hex}",
    )
    provider = provider or configured_email_provider()
    provisional = AuthEmailDelivery(outbox=event, available_at=now)
    provisional.outbox = event
    prepared = _prepare(provider, message_for_auth_delivery(provisional))
    AuthEmailDelivery.objects.create(
        outbox=event,
        available_at=now,
        provider_contract_id=prepared.transport.contract_id,
        provider_serializer_version=prepared.transport.serializer_version,
        provider_idempotency_namespace=prepared.transport.idempotency_namespace,
        provider_payload_hash=hashlib.sha256(prepared.body).hexdigest(),
    )
    return event


def _select_for_update_skip_locked(queryset):
    if connection.features.has_select_for_update_skip_locked:
        return queryset.select_for_update(skip_locked=True)
    return queryset.select_for_update()


def _is_current(delivery, now):
    credential = delivery.outbox.credential
    user = delivery.outbox.user
    if (
        credential.used_at is not None
        or credential.revoked_at is not None
        or now >= credential.expires_at
        or not user.is_active
        or user.is_banned
        or credential.auth_state_version != user.auth_state_version
        or credential.email_normalized != user.email_normalized
    ):
        return False
    if credential.purpose == AuthCredential.Purpose.PASSWORD_RESET:
        return _has_verified_primary_identity(user)
    return not _has_verified_primary_identity(user)


def _retry_delay(attempt_count):
    return min(
        settings.EMAIL_OUTBOX_RETRY_MAX_SECONDS,
        settings.EMAIL_OUTBOX_RETRY_BASE_SECONDS * (2 ** min(max(0, attempt_count - 1), 20)),
    )


def _claim_delivery(delivery_id, *, at=None):
    now = at or timezone.now()
    stale = now - timedelta(seconds=settings.EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS)
    with transaction.atomic():
        delivery = (
            AuthEmailDelivery.objects.select_for_update()
            .select_related("outbox", "outbox__credential", "outbox__user")
            .get(pk=delivery_id)
        )
        claimable = (
            delivery.status == AuthEmailDelivery.Status.PENDING and delivery.available_at <= now
        ) or (
            delivery.status == AuthEmailDelivery.Status.PROCESSING
            and delivery.processing_at is not None
            and delivery.processing_at <= stale
        )
        if not claimable:
            return None
        if (
            delivery.first_provider_attempt_at is not None
            and now
            >= delivery.first_provider_attempt_at
            + timedelta(seconds=settings.EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS)
        ):
            delivery.status = AuthEmailDelivery.Status.MANUAL_REVIEW
            delivery.processing_at = None
            delivery.ambiguity_reason = "window_expired"
            delivery.last_error = "Provider ambiguity exceeded the idempotency safety window"
            delivery.save(
                update_fields=(
                    "status",
                    "processing_at",
                    "ambiguity_reason",
                    "last_error",
                    "updated_at",
                )
            )
            AuthEmailOutbox.objects.filter(pk=delivery.outbox_id).update(
                status=AuthEmailOutbox.Status.FAILED,
                processing_at=None,
                last_error="Provider ambiguity exceeded the idempotency safety window",
            )
            return None
        if not _is_current(delivery, now):
            delivery.status = (
                AuthEmailDelivery.Status.MANUAL_REVIEW
                if delivery.first_provider_attempt_at
                else AuthEmailDelivery.Status.FAILED
            )
            delivery.processing_at = None
            delivery.ambiguity_reason = (
                "account_changed" if delivery.first_provider_attempt_at else ""
            )
            delivery.last_error = "Auth email is no longer deliverable"
            delivery.save(
                update_fields=(
                    "status",
                    "processing_at",
                    "ambiguity_reason",
                    "last_error",
                    "updated_at",
                )
            )
            AuthEmailOutbox.objects.filter(pk=delivery.outbox_id).update(
                status=AuthEmailOutbox.Status.FAILED,
                processing_at=None,
                last_error="Auth email is no longer deliverable",
            )
            return None
        delivery.status = AuthEmailDelivery.Status.PROCESSING
        delivery.processing_at = now
        delivery.attempt_count += 1
        delivery.last_error = ""
        delivery.save(
            update_fields=(
                "status",
                "processing_at",
                "attempt_count",
                "last_error",
                "updated_at",
            )
        )
        AuthEmailOutbox.objects.filter(pk=delivery.outbox_id).update(
            status=AuthEmailOutbox.Status.PROCESSING,
            processing_at=now,
            attempt_count=delivery.attempt_count,
            last_error="",
        )
        return delivery


def _failure(delivery, error, *, at=None):
    now = at or timezone.now()
    with transaction.atomic():
        current = AuthEmailDelivery.objects.select_for_update().get(pk=delivery.pk)
        # A stale worker may finish after another claimant has already settled
        # the provider result. Never downgrade a terminal delivery (especially
        # SENT) based on that older attempt.
        if current.status != AuthEmailDelivery.Status.PROCESSING:
            return
        terminal = (
            not error.retryable or current.attempt_count >= settings.EMAIL_OUTBOX_MAX_ATTEMPTS
        )
        current.status = (
            AuthEmailDelivery.Status.FAILED if terminal else AuthEmailDelivery.Status.PENDING
        )
        current.processing_at = None
        current.last_error = error.safe_message[:500]
        current.ambiguity_reason = error.ambiguity_reason[:40]
        fields = [
            "status",
            "processing_at",
            "last_error",
            "ambiguity_reason",
            "updated_at",
        ]
        if not terminal:
            current.available_at = now + timedelta(seconds=_retry_delay(current.attempt_count))
            fields.append("available_at")
        current.save(update_fields=fields)
        AuthEmailOutbox.objects.filter(pk=current.outbox_id).update(
            status=(AuthEmailOutbox.Status.FAILED if terminal else AuthEmailOutbox.Status.PENDING),
            processing_at=None,
            available_at=current.available_at,
            last_error=error.safe_message[:500],
        )


def _mark_manual_review(delivery, *, reason, message):
    with transaction.atomic():
        current = AuthEmailDelivery.objects.select_for_update().get(pk=delivery.pk)
        if current.status != AuthEmailDelivery.Status.PROCESSING:
            return
        current.status = AuthEmailDelivery.Status.MANUAL_REVIEW
        current.processing_at = None
        current.ambiguity_reason = reason[:40]
        current.last_error = message[:500]
        current.save(
            update_fields=(
                "status",
                "processing_at",
                "ambiguity_reason",
                "last_error",
                "updated_at",
            )
        )
        AuthEmailOutbox.objects.filter(pk=current.outbox_id).update(
            status=AuthEmailOutbox.Status.FAILED,
            processing_at=None,
            last_error=message[:500],
        )


def process_auth_email_delivery(delivery_id, *, provider=None, at=None):
    now = at or timezone.now()
    delivery = _claim_delivery(delivery_id, at=now)
    if delivery is None:
        return False
    provider = provider or configured_email_provider()
    current = AuthEmailDelivery.objects.select_related(
        "outbox", "outbox__credential", "outbox__user"
    ).get(pk=delivery.pk)
    try:
        prepared = _prepare(provider, message_for_auth_delivery(current))
    except Exception:
        _mark_manual_review(
            current,
            reason="payload_mismatch",
            message="Immutable auth email could not be rendered",
        )
        return False
    if (
        prepared.transport.contract_id != current.provider_contract_id
        or prepared.transport.serializer_version != current.provider_serializer_version
        or prepared.transport.idempotency_namespace != current.provider_idempotency_namespace
        or hashlib.sha256(prepared.body).hexdigest() != current.provider_payload_hash
    ):
        _mark_manual_review(
            current,
            reason="payload_mismatch",
            message="Auth email transport identity changed",
        )
        return False
    if current.first_provider_attempt_at is None:
        current.first_provider_attempt_at = now
    current.last_provider_attempt_at = now
    current.save(
        update_fields=(
            "first_provider_attempt_at",
            "last_provider_attempt_at",
            "updated_at",
        )
    )
    try:
        result = provider.send(prepared, current.provider_idempotency_key)
    except EmailProviderError as error:
        _failure(current, error, at=now)
        return False
    except Exception as error:  # pragma: no cover - defensive provider boundary
        _failure(
            current,
            EmailProviderError(
                f"Email provider failure ({type(error).__name__})",
                retryable=True,
            ),
            at=now,
        )
        return False
    with transaction.atomic():
        settling = AuthEmailDelivery.objects.select_for_update().get(pk=current.pk)
        if settling.status != AuthEmailDelivery.Status.PROCESSING:
            return False
        settling.status = AuthEmailDelivery.Status.SENT
        settling.processing_at = None
        settling.provider_message_id = result.message_id
        settling.sent_at = now
        settling.last_error = ""
        settling.ambiguity_reason = ""
        settling.save(
            update_fields=(
                "status",
                "processing_at",
                "provider_message_id",
                "sent_at",
                "last_error",
                "ambiguity_reason",
                "updated_at",
            )
        )
        AuthEmailOutbox.objects.filter(pk=settling.outbox_id).update(
            status=AuthEmailOutbox.Status.DELIVERED,
            processing_at=None,
            delivered_at=now,
            last_error="",
        )
    return True


def process_auth_email_batch(*, limit, provider=None, at=None):
    now = at or timezone.now()
    stale = now - timedelta(seconds=settings.EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS)
    with transaction.atomic():
        queryset = AuthEmailDelivery.objects.filter(
            Q(status=AuthEmailDelivery.Status.PENDING, available_at__lte=now)
            | Q(
                status=AuthEmailDelivery.Status.PROCESSING,
                processing_at__lte=stale,
            )
        ).order_by("available_at", "created_at", "id")
        ids = list(_select_for_update_skip_locked(queryset).values_list("pk", flat=True)[:limit])
    sent = 0
    for delivery_id in ids:
        sent += int(process_auth_email_delivery(delivery_id, provider=provider, at=now))
    return sent
