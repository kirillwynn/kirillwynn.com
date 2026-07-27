from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.subscriptions.models import (
    EmailDelivery,
    EmailOutbox,
    Subscriber,
    normalize_email_address,
)

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
    )
    EmailDelivery.objects.create(
        outbox=outbox,
        subscriber=subscriber,
        available_at=now,
    )

    with pytest.raises(ProtectedError):
        subscriber.delete()
    with pytest.raises(ProtectedError):
        outbox.delete()
    with pytest.raises(ProtectedError):
        blog_post.delete()
