import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
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
    )
    delivery = EmailDelivery.objects.create(
        outbox=outbox,
        subscriber=subscriber,
        status=EmailDelivery.Status.SENT,
        available_at=now,
        provider_message_id=message_id or f"message-{uuid.uuid4()}",
        sent_at=now,
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


def event_payload(event_type, message_id):
    payload = {
        "type": event_type,
        "created_at": timezone.now().isoformat(),
        "data": {"email_id": message_id},
    }
    if event_type == "email.bounced":
        payload["data"]["bounce"] = {
            "type": "Permanent",
            "subType": "General",
            "message": "raw provider detail must not persist",
        }
    return payload


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
