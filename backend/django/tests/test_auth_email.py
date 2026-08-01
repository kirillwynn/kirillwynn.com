import hashlib
import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.subscriptions.models import EmailOutbox, Subscriber
from apps.subscriptions.providers.base import (
    EmailProvider,
    EmailProviderError,
    ProviderSendResult,
)
from apps.subscriptions.providers.memory import MemoryEmailProvider
from apps.users.auth_email import (
    _failure,
    message_for_auth_delivery,
    process_auth_email_batch,
    process_auth_email_delivery,
    queue_auth_email,
)
from apps.users.credentials import issue_credential
from apps.users.models import AuthCredential, AuthEmailDelivery, AuthEmailOutbox
from tests.identity import create_identity_user

pytestmark = pytest.mark.django_db


class RecordingProvider(EmailProvider):
    transport_contract_id = "recording.email"
    serializer_contract_version = 1

    def __init__(self):
        self.calls = []

    def send(self, prepared_request, idempotency_key):
        self.calls.append((prepared_request, idempotency_key))
        return ProviderSendResult(message_id=f"recorded-{len(self.calls)}")


class FailingProvider(RecordingProvider):
    def __init__(self, *, retryable=True, ambiguity_reason="provider_failure"):
        super().__init__()
        self.retryable = retryable
        self.ambiguity_reason = ambiguity_reason

    def send(self, prepared_request, idempotency_key):
        self.calls.append((prepared_request, idempotency_key))
        raise EmailProviderError(
            "Bounded provider failure",
            retryable=self.retryable,
            ambiguity_reason=self.ambiguity_reason,
        )


def test_auth_email_uses_separate_durable_contract_and_fragment_only_credential():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )

    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.VERIFY_EMAIL)
    delivery = AuthEmailDelivery.objects.get(outbox=event)
    raw = issue_credential(event.credential)
    message = message_for_auth_delivery(delivery)
    serialized = json.dumps(
        {
            "outbox": list(AuthEmailOutbox.objects.values()),
            "credential": list(AuthCredential.objects.values()),
            "delivery": list(AuthEmailDelivery.objects.values()),
        },
        default=str,
    )

    assert event.message_type == AuthEmailOutbox.MessageType.EMAIL_VERIFICATION
    assert event.snapshot_subject == "Verify your email address"
    assert event.snapshot_recipient_email == "reader@example.com"
    assert event.user_id == user.pk
    assert event.credential.user_id == user.pk
    assert delivery.provider_idempotency_namespace.endswith("/auth")
    assert delivery.provider_idempotency_key.startswith(
        f"{delivery.provider_idempotency_namespace}/"
    )
    assert delivery.provider_idempotency_key.endswith(delivery.pk.hex)
    assert "#credential=" in message.text and "#credential=" in message.html
    assert "?credential=" not in message.text and "?credential=" not in message.html
    assert raw in message.text
    assert raw not in serialized
    assert Subscriber.objects.count() == 0
    assert EmailOutbox.objects.count() == 0


def test_worker_sends_exact_attested_bytes_once_without_web_provider_io():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    provider = RecordingProvider()
    event = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        provider=provider,
    )

    # Queueing serializes the immutable request but performs no provider I/O.
    assert provider.calls == []
    delivery = AuthEmailDelivery.objects.get(outbox=event)
    sent = process_auth_email_delivery(delivery.pk, provider=provider)
    repeated = process_auth_email_delivery(delivery.pk, provider=provider)

    delivery.refresh_from_db()
    event.refresh_from_db()
    assert sent is True and repeated is False
    assert len(provider.calls) == 1
    prepared, key = provider.calls[0]
    assert hashlib.sha256(prepared.body).hexdigest() == delivery.provider_payload_hash
    assert prepared.transport.idempotency_namespace == delivery.provider_idempotency_namespace
    assert key == delivery.provider_idempotency_key
    assert delivery.status == AuthEmailDelivery.Status.SENT
    assert event.status == AuthEmailOutbox.Status.DELIVERED


def test_retryable_and_terminal_provider_failures_have_bounded_safe_state():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    retrying = FailingProvider(retryable=True, ambiguity_reason="transport_failure")
    event = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        provider=retrying,
    )
    delivery = event.delivery
    first_at = timezone.now()

    assert process_auth_email_delivery(delivery.pk, provider=retrying, at=first_at) is False
    delivery.refresh_from_db()
    assert delivery.status == AuthEmailDelivery.Status.PENDING
    assert delivery.available_at > first_at
    assert delivery.last_error == "Bounded provider failure"
    assert delivery.ambiguity_reason == "transport_failure"

    terminal_user = create_identity_user(
        username="terminal",
        email="terminal@example.com",
        nickname="Terminal Reader",
        verified=False,
    )
    terminal = FailingProvider(retryable=False)
    terminal_event = queue_auth_email(
        user=terminal_user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        provider=terminal,
    )
    assert process_auth_email_delivery(terminal_event.delivery.pk, provider=terminal) is False
    terminal_event.delivery.refresh_from_db()
    terminal_event.refresh_from_db()
    assert terminal_event.delivery.status == AuthEmailDelivery.Status.FAILED
    assert terminal_event.status == AuthEmailOutbox.Status.FAILED
    assert len(terminal_event.delivery.last_error) <= 500


def test_account_change_after_ambiguous_attempt_requires_manual_review_without_resend():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    failing = FailingProvider(retryable=True, ambiguity_reason="transport_failure")
    event = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        provider=failing,
    )
    delivery = event.delivery
    first_at = timezone.now()
    process_auth_email_delivery(delivery.pk, provider=failing, at=first_at)
    user.auth_state_version += 1
    user.save(update_fields=("auth_state_version",))
    delivery.refresh_from_db()

    assert (
        process_auth_email_delivery(
            delivery.pk,
            provider=failing,
            at=delivery.available_at + timedelta(seconds=1),
        )
        is False
    )
    delivery.refresh_from_db()
    event.refresh_from_db()
    assert len(failing.calls) == 1
    assert delivery.status == AuthEmailDelivery.Status.MANUAL_REVIEW
    assert delivery.ambiguity_reason == "account_changed"
    assert event.status == AuthEmailOutbox.Status.FAILED


@override_settings(EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS=10)
def test_auth_email_never_retries_after_provider_idempotency_window():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    provider = FailingProvider(retryable=True, ambiguity_reason="transport_failure")
    event = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        provider=provider,
    )
    first_at = timezone.now()

    assert process_auth_email_delivery(event.delivery.pk, provider=provider, at=first_at) is False
    event.delivery.refresh_from_db()
    assert (
        process_auth_email_delivery(
            event.delivery.pk,
            provider=provider,
            at=event.delivery.available_at + timedelta(seconds=1),
        )
        is False
    )

    event.delivery.refresh_from_db()
    event.refresh_from_db()
    assert len(provider.calls) == 1
    assert event.delivery.status == AuthEmailDelivery.Status.MANUAL_REVIEW
    assert event.delivery.ambiguity_reason == "window_expired"
    assert "idempotency safety window" in event.delivery.last_error
    assert event.status == AuthEmailOutbox.Status.FAILED


def test_resend_revokes_old_credential_and_stale_delivery_never_reaches_provider():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    provider = RecordingProvider()
    first = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        provider=provider,
    )
    second = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        provider=provider,
    )
    first.credential.refresh_from_db()

    assert first.credential.revoked_at is not None
    assert process_auth_email_delivery(first.delivery.pk, provider=provider) is False
    assert process_auth_email_delivery(second.delivery.pk, provider=provider) is True
    assert len(provider.calls) == 1


def test_password_reset_email_requires_verified_primary_and_uses_distinct_type():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    assert queue_auth_email(user=user, purpose=AuthCredential.Purpose.PASSWORD_RESET) is None
    user.emailaddress_set.update(verified=True)

    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.PASSWORD_RESET)
    delivery = event.delivery
    message = message_for_auth_delivery(delivery)

    assert event.message_type == AuthEmailOutbox.MessageType.PASSWORD_RESET
    assert event.snapshot_subject == "Reset your account password"
    assert "/account/password/reset/confirm#credential=" in message.text
    assert "verify-email" not in message.text


def test_worker_batch_and_command_are_bounded_and_do_not_log_credentials(capsys):
    MemoryEmailProvider.reset()
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.VERIFY_EMAIL)
    raw = issue_credential(event.credential)

    assert process_auth_email_batch(limit=1) == 1
    assert process_auth_email_batch(limit=1) == 0
    call_command("process_auth_email_outbox", limit=1)

    output = capsys.readouterr().out
    assert "auth_email_sent=0" in output
    assert raw not in output
    assert len(MemoryEmailProvider.sent) == 1


@override_settings(EMAIL_OUTBOX_MAX_ATTEMPTS=1)
def test_retryable_failure_becomes_terminal_at_attempt_limit():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    provider = FailingProvider(retryable=True)
    event = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        provider=provider,
    )

    process_auth_email_delivery(event.delivery.pk, provider=provider)
    event.delivery.refresh_from_db()

    assert event.delivery.status == AuthEmailDelivery.Status.FAILED


def test_stale_worker_failure_cannot_downgrade_a_settled_delivery():
    user = create_identity_user(
        username="stale-worker-reader",
        email="stale-worker@example.com",
        nickname="Stale Worker Reader",
        verified=False,
    )
    provider = RecordingProvider()
    event = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        provider=provider,
    )
    settled_at = timezone.now()
    AuthEmailDelivery.objects.filter(pk=event.delivery.pk).update(
        status=AuthEmailDelivery.Status.SENT,
        processing_at=None,
        sent_at=settled_at,
        provider_message_id="already-settled",
    )
    AuthEmailOutbox.objects.filter(pk=event.pk).update(
        status=AuthEmailOutbox.Status.DELIVERED,
        processing_at=None,
        delivered_at=settled_at,
    )

    _failure(
        event.delivery,
        EmailProviderError(
            "Older attempt timed out",
            retryable=True,
            ambiguity_reason="transport_failure",
        ),
    )

    event.delivery.refresh_from_db()
    event.refresh_from_db()
    assert event.delivery.status == AuthEmailDelivery.Status.SENT
    assert event.status == AuthEmailOutbox.Status.DELIVERED
