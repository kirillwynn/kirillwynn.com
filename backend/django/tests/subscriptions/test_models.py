from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.subscriptions.models import (
    EmailDelivery,
    EmailOutbox,
    EmailWebhookEvent,
    Subscriber,
    normalize_email_address,
)
from apps.subscriptions.outbox import publication_outbox_snapshot

pytestmark = pytest.mark.django_db


def test_email_normalization_trims_casefolds_and_idna_normalizes_domain():
    source, canonical = normalize_email_address("  Reader@BÜCHER.de  ")

    assert source == "Reader@BÜCHER.de"
    assert canonical == "reader@xn--bcher-kva.de"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-an-email",
        "a@@example.com",
        "a@example.com/path",
        f"{'a' * 310}@example.com",
    ],
)
def test_email_normalization_rejects_invalid_or_oversized_values(value):
    with pytest.raises(Exception):
        normalize_email_address(value)


def test_canonical_email_is_case_insensitively_unique():
    Subscriber.objects.create(email="Reader@Example.com")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Subscriber.objects.create(email="reader@example.COM")


def test_subscriber_lifecycle_constraint_rejects_impossible_timestamp_shape():
    subscriber = Subscriber.objects.create(email="reader@example.com")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Subscriber.objects.filter(pk=subscriber.pk).update(
                status=Subscriber.Status.ACTIVE,
                confirmed_at=None,
            )


def test_outbox_message_and_status_constraints(blog_post):
    now = timezone.now()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailOutbox.objects.create(
                message_type=EmailOutbox.MessageType.PUBLICATION,
                post=blog_post,
                audience_cutoff=None,
                available_at=now,
                idempotency_key="invalid-publication",
            )


def test_delivery_history_protects_subscriber_outbox_and_post(blog_post):
    now = timezone.now()
    subscriber = Subscriber.objects.create(
        email="reader@example.com",
        status=Subscriber.Status.ACTIVE,
        confirmed_at=now - timedelta(minutes=1),
    )
    outbox = EmailOutbox.objects.create(
        message_type=EmailOutbox.MessageType.PUBLICATION,
        post=blog_post,
        audience_cutoff=now,
        available_at=now,
        idempotency_key=f"publication/{blog_post.pk}",
        **publication_outbox_snapshot(blog_post),
    )
    EmailDelivery.objects.create(
        outbox=outbox,
        subscriber=subscriber,
        available_at=now,
        snapshot_recipient_email=subscriber.email,
        snapshot_credential_version=subscriber.unsubscribe_token_version,
        credential_issued_at=now,
        provider_payload_hash="0" * 64,
    )

    with pytest.raises(ProtectedError):
        subscriber.delete()
    with pytest.raises(ProtectedError):
        outbox.delete()
    with pytest.raises(ProtectedError):
        blog_post.delete()


def test_delivery_attempt_and_manual_review_constraints(blog_post):
    now = timezone.now()
    subscriber = Subscriber.objects.create(
        email="constraint@example.com",
        status=Subscriber.Status.ACTIVE,
        confirmed_at=now - timedelta(minutes=1),
    )
    outbox = EmailOutbox.objects.create(
        message_type=EmailOutbox.MessageType.PUBLICATION,
        post=blog_post,
        audience_cutoff=now,
        available_at=now,
        idempotency_key=f"constraint/{blog_post.pk}",
        **publication_outbox_snapshot(blog_post),
    )
    common = {
        "outbox": outbox,
        "subscriber": subscriber,
        "available_at": now,
        "snapshot_recipient_email": subscriber.email,
        "snapshot_credential_version": subscriber.unsubscribe_token_version,
        "credential_issued_at": now,
        "provider_payload_hash": "0" * 64,
    }

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailDelivery.objects.create(
                **common,
                first_provider_attempt_at=now,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailDelivery.objects.create(
                **common,
                status=EmailDelivery.Status.MANUAL_REVIEW,
            )


def test_pending_webhook_constraint_requires_bounded_correlation_identity():
    now = timezone.now()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailWebhookEvent.objects.create(
                event_id="invalid-pending",
                event_type="email.delivered",
                processing_state=EmailWebhookEvent.ProcessingState.PENDING,
                expires_at=now + timedelta(days=7),
            )
