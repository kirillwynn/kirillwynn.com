import io
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from svix.webhooks import Webhook

from apps.subscriptions.models import (
    EmailDelivery,
    EmailOutbox,
    EmailWebhookEvent,
    Subscriber,
)
from apps.subscriptions.outbox import (
    build_delivery_batch,
    claim_outbox_batch,
    process_outbox_event,
    publication_outbox_snapshot,
)
from apps.subscriptions.providers.base import EmailProvider, ProviderSendResult
from apps.subscriptions.webhooks import expire_unmatched_webhooks

pytestmark = pytest.mark.django_db


def sent_delivery(blog_post, email="reader@example.com", message_id=None):
    now = timezone.now()
    subscriber = Subscriber.objects.create(
        email=email,
        status=Subscriber.Status.ACTIVE,
        confirmed_at=now - timedelta(days=1),
    )
    outbox = EmailOutbox.objects.create(
        message_type=EmailOutbox.MessageType.PUBLICATION,
        post=blog_post,
        audience_cutoff=now,
        available_at=now,
        idempotency_key=f"publication/{blog_post.pk}/{email}",
        **publication_outbox_snapshot(blog_post),
    )
    delivery = EmailDelivery.objects.create(
        outbox=outbox,
        subscriber=subscriber,
        status=EmailDelivery.Status.SENT,
        available_at=now,
        provider_message_id=message_id or f"message-{uuid.uuid4()}",
        sent_at=now,
        snapshot_recipient_email=subscriber.email,
        snapshot_credential_version=subscriber.unsubscribe_token_version,
        credential_issued_at=now,
        provider_payload_hash="0" * 64,
        first_provider_attempt_at=now,
        last_provider_attempt_at=now,
    )
    return subscriber, delivery


def signed_webhook(
    payload,
    *,
    event_id="event-1",
    timestamp=None,
    body=None,
    signature_body=None,
):
    timestamp = timestamp or datetime.now(tz=UTC)
    raw_body = body or json.dumps(payload, separators=(",", ":")).encode()
    signed_body = signature_body or raw_body
    signature = Webhook("whsec_dGVzdC13ZWJob29rLXNlY3JldC0zMi1ieXRlcy0wMQ==").sign(
        event_id, timestamp, signed_body.decode()
    )
    return APIClient().post(
        reverse("subscriptions_api:resend-webhook"),
        raw_body,
        content_type="application/json",
        HTTP_SVIX_ID=event_id,
        HTTP_SVIX_TIMESTAMP=str(int(timestamp.timestamp())),
        HTTP_SVIX_SIGNATURE=signature,
    )


def event_payload(event_type, message_id, *, occurred_at=None):
    payload = {
        "type": event_type,
        "created_at": (occurred_at or timezone.now()).isoformat(),
        "data": {"email_id": message_id},
    }
    if event_type == "email.bounced":
        payload["data"]["bounce"] = {
            "type": "Permanent",
            "subType": "General",
            "message": "raw provider detail must not persist",
        }
    return payload


class FixedProvider(EmailProvider):
    def __init__(self, message_id):
        self.message_id = message_id
        self.calls = 0

    def send(self, message, idempotency_key):
        self.calls += 1
        return ProviderSendResult(message_id=self.message_id)


def pending_worker_delivery(blog_post):
    now = timezone.now()
    subscriber = Subscriber.objects.create(
        email=f"early-{blog_post.pk}@example.com",
        status=Subscriber.Status.ACTIVE,
        confirmed_at=now - timedelta(days=1),
    )
    blog_post.save_revision().publish()
    event = EmailOutbox.objects.get(
        post=blog_post,
        message_type=EmailOutbox.MessageType.PUBLICATION,
    )
    worker_now = timezone.now()
    claim_outbox_batch(limit=1, at=worker_now)
    delivery_id = build_delivery_batch(event.pk, limit=1, at=worker_now)[0]
    return subscriber, event, EmailDelivery.objects.get(pk=delivery_id)


def test_valid_delivered_webhook_updates_only_provider_message_match(blog_post):
    _, delivery = sent_delivery(blog_post)

    response = signed_webhook(event_payload("email.delivered", delivery.provider_message_id))

    assert response.status_code == 200
    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.DELIVERED
    assert delivery.delivered_at is not None
    event = EmailWebhookEvent.objects.get()
    assert event.delivery == delivery
    assert event.event_type == "email.delivered"


def test_webhook_rejects_tampering_missing_signature_and_old_timestamp(blog_post):
    _, delivery = sent_delivery(blog_post)
    payload = event_payload("email.delivered", delivery.provider_message_id)
    valid_body = json.dumps(payload, separators=(",", ":")).encode()
    tampered = signed_webhook(
        payload,
        body=valid_body + b" ",
        signature_body=valid_body,
    )
    missing = APIClient().post(
        reverse("subscriptions_api:resend-webhook"),
        valid_body,
        content_type="application/json",
    )
    old = signed_webhook(
        payload,
        event_id="old-event",
        timestamp=datetime.now(tz=UTC) - timedelta(minutes=6),
    )

    assert tampered.status_code == missing.status_code == old.status_code == 400
    assert EmailWebhookEvent.objects.count() == 0
    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.SENT


def test_webhook_event_id_is_idempotent(blog_post):
    _, delivery = sent_delivery(blog_post)
    payload = event_payload("email.delivered", delivery.provider_message_id)

    first = signed_webhook(payload, event_id="duplicate-event")
    second = signed_webhook(payload, event_id="duplicate-event")

    assert first.status_code == second.status_code == 200
    assert EmailWebhookEvent.objects.count() == 1


@pytest.mark.parametrize(
    ("event_type", "expected_status", "reason"),
    [
        ("email.bounced", EmailDelivery.Status.BOUNCED, "hard_bounce"),
        ("email.complained", EmailDelivery.Status.COMPLAINED, "complaint"),
    ],
)
def test_bounce_and_complaint_suppress_subscriber(
    blog_post,
    event_type,
    expected_status,
    reason,
):
    subscriber, delivery = sent_delivery(blog_post)

    response = signed_webhook(
        event_payload(event_type, delivery.provider_message_id),
        event_id=event_type,
    )

    assert response.status_code == 200
    subscriber.refresh_from_db()
    delivery.refresh_from_db()
    assert delivery.status == expected_status
    assert subscriber.status == Subscriber.Status.SUPPRESSED
    assert subscriber.suppression_reason == reason
    assert "raw provider detail" not in delivery.bounce_type


def test_late_delivered_event_cannot_override_complaint(blog_post):
    _, delivery = sent_delivery(blog_post)
    signed_webhook(
        event_payload("email.complained", delivery.provider_message_id),
        event_id="complaint-first",
    )
    signed_webhook(
        event_payload("email.delivered", delivery.provider_message_id),
        event_id="delivered-late",
    )

    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.COMPLAINED


def test_unknown_type_and_message_id_are_safe_successes(blog_post):
    subscriber, delivery = sent_delivery(blog_post)
    unknown_type = signed_webhook(
        event_payload("email.opened", delivery.provider_message_id),
        event_id="unknown-type",
    )
    unknown_message = signed_webhook(
        event_payload("email.bounced", "not-our-message"),
        event_id="unknown-message",
    )

    assert unknown_type.status_code == unknown_message.status_code == 200
    assert EmailWebhookEvent.objects.count() == 2
    subscriber.refresh_from_db()
    delivery.refresh_from_db()
    assert subscriber.status == Subscriber.Status.ACTIVE
    assert delivery.status == EmailDelivery.Status.SENT
    foreign = EmailWebhookEvent.objects.get(event_id="unknown-message")
    assert foreign.processing_state == EmailWebhookEvent.ProcessingState.PENDING
    assert foreign.provider_message_id == "not-our-message"


@override_settings(RESEND_WEBHOOK_MAX_BODY_BYTES=32)
def test_webhook_rejects_oversized_body_before_processing():
    response = APIClient().post(
        reverse("subscriptions_api:resend-webhook"),
        b"x" * 33,
        content_type="application/json",
        HTTP_SVIX_ID="large",
        HTTP_SVIX_TIMESTAMP=str(int(timezone.now().timestamp())),
        HTTP_SVIX_SIGNATURE="v1,invalid",
    )

    assert response.status_code == 413
    assert EmailWebhookEvent.objects.count() == 0


def test_webhook_before_provider_id_is_reconciled_by_worker(blog_post):
    _, event, delivery = pending_worker_delivery(blog_post)
    message_id = "early-delivered-message"
    response = signed_webhook(
        event_payload("email.delivered", message_id),
        event_id="early-delivered",
    )
    webhook = EmailWebhookEvent.objects.get(event_id="early-delivered")
    assert response.status_code == 200
    assert webhook.processing_state == EmailWebhookEvent.ProcessingState.PENDING
    assert webhook.delivery is None

    provider = FixedProvider(message_id)
    sent, _ = process_outbox_event(event.pk, provider=provider)

    delivery.refresh_from_db()
    webhook.refresh_from_db()
    assert sent == 1
    assert provider.calls == 1
    assert delivery.status == EmailDelivery.Status.DELIVERED
    assert webhook.processing_state == EmailWebhookEvent.ProcessingState.APPLIED
    assert webhook.delivery == delivery


@pytest.mark.parametrize(
    ("event_type", "expected_status", "reason"),
    [
        ("email.bounced", EmailDelivery.Status.BOUNCED, "hard_bounce"),
        ("email.complained", EmailDelivery.Status.COMPLAINED, "complaint"),
    ],
)
def test_early_bounce_and_complaint_suppress_after_worker_correlation(
    blog_post,
    event_type,
    expected_status,
    reason,
):
    subscriber, event, delivery = pending_worker_delivery(blog_post)
    message_id = f"early-{expected_status}"
    signed_webhook(
        event_payload(event_type, message_id),
        event_id=f"event-{expected_status}",
    )

    process_outbox_event(event.pk, provider=FixedProvider(message_id))

    subscriber.refresh_from_db()
    delivery.refresh_from_db()
    assert subscriber.status == Subscriber.Status.SUPPRESSED
    assert subscriber.suppression_reason == reason
    assert delivery.status == expected_status


def test_duplicate_early_webhook_stays_one_pending_event(blog_post):
    _, _, _ = pending_worker_delivery(blog_post)
    payload = event_payload("email.delivered", "early-duplicate-message")

    first = signed_webhook(payload, event_id="early-duplicate")
    second = signed_webhook(payload, event_id="early-duplicate")

    assert first.status_code == second.status_code == 200
    assert EmailWebhookEvent.objects.filter(event_id="early-duplicate").count() == 1
    assert (
        EmailWebhookEvent.objects.get(event_id="early-duplicate").processing_state
        == EmailWebhookEvent.ProcessingState.PENDING
    )


def test_out_of_order_early_events_apply_deterministically_and_complaint_wins(
    blog_post,
):
    subscriber, event, delivery = pending_worker_delivery(blog_post)
    message_id = "early-out-of-order"
    base = timezone.now()
    signed_webhook(
        event_payload(
            "email.complained",
            message_id,
            occurred_at=base + timedelta(seconds=3),
        ),
        event_id="complaint-out-of-order",
    )
    signed_webhook(
        event_payload("email.delivered", message_id, occurred_at=base),
        event_id="delivered-out-of-order",
    )
    signed_webhook(
        event_payload(
            "email.bounced",
            message_id,
            occurred_at=base + timedelta(seconds=2),
        ),
        event_id="bounce-out-of-order",
    )

    process_outbox_event(event.pk, provider=FixedProvider(message_id))

    subscriber.refresh_from_db()
    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.COMPLAINED
    assert subscriber.status == Subscriber.Status.SUPPRESSED
    assert subscriber.suppression_reason == "complaint"
    assert not EmailWebhookEvent.objects.filter(
        provider_message_id=message_id,
        processing_state=EmailWebhookEvent.ProcessingState.PENDING,
    ).exists()


def test_foreign_webhook_expires_without_retry_storm(blog_post):
    response = signed_webhook(
        event_payload("email.delivered", "foreign-provider-message"),
        event_id="foreign-expiry",
    )
    event = EmailWebhookEvent.objects.get(event_id="foreign-expiry")

    expired = expire_unmatched_webhooks(limit=10, at=event.expires_at)

    event.refresh_from_db()
    assert response.status_code == 200
    assert expired == 1
    assert event.processing_state == EmailWebhookEvent.ProcessingState.IGNORED
    assert event.delivery is None


def test_management_reconciliation_recovers_after_worker_crash(blog_post):
    _, _, delivery = pending_worker_delivery(blog_post)
    message_id = "crash-before-reconciliation"
    signed_webhook(
        event_payload("email.delivered", message_id),
        event_id="crash-event",
    )
    now = timezone.now()
    EmailDelivery.objects.filter(pk=delivery.pk).update(
        status=EmailDelivery.Status.SENT,
        processing_at=None,
        provider_message_id=message_id,
        sent_at=now,
        first_provider_attempt_at=now,
        last_provider_attempt_at=now,
    )
    output = io.StringIO()

    call_command("reconcile_email_webhooks", limit=10, stdout=output)

    delivery.refresh_from_db()
    event = EmailWebhookEvent.objects.get(event_id="crash-event")
    assert delivery.status == EmailDelivery.Status.DELIVERED
    assert event.processing_state == EmailWebhookEvent.ProcessingState.APPLIED
    assert "Reconciled 1" in output.getvalue()


def test_webhook_storage_contains_only_normalized_fields_not_raw_payload(blog_post):
    _, delivery = sent_delivery(blog_post)
    signed_webhook(
        event_payload("email.bounced", delivery.provider_message_id),
        event_id="bounded-bounce",
    )
    event = EmailWebhookEvent.objects.get(event_id="bounded-bounce")
    stored_text = " ".join(
        str(value)
        for value in (
            event.event_id,
            event.event_type,
            event.provider_message_id,
            event.bounce_type,
            event.processing_state,
        )
    )

    assert event.bounce_type == "permanent"
    assert "raw provider detail must not persist" not in stored_text
    assert not any(field.name in {"payload", "raw_body", "data"} for field in event._meta.fields)
