from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.subscriptions.models import (
    EmailDelivery,
    EmailOutbox,
    Subscriber,
    normalize_email_address,
)
from apps.subscriptions.tokens import (
    InvalidSubscriptionCredential,
    read_credential,
)


def _confirmation_event(subscriber, now):
    return EmailOutbox.objects.create(
        message_type=EmailOutbox.MessageType.CONFIRMATION,
        subscriber=subscriber,
        credential_version=subscriber.confirmation_token_version,
        available_at=now,
        idempotency_key=(f"confirmation/{subscriber.pk}/{subscriber.confirmation_token_version}"),
    )


@transaction.atomic
def request_subscription(email, *, at=None):
    source, canonical = normalize_email_address(email)
    now = at or timezone.now()
    try:
        subscriber = Subscriber.objects.select_for_update().get(canonical_email=canonical)
    except Subscriber.DoesNotExist:
        try:
            with transaction.atomic():
                subscriber = Subscriber.objects.create(
                    email=source,
                    canonical_email=canonical,
                    status=Subscriber.Status.PENDING,
                    confirmation_sent_at=now,
                )
        except IntegrityError:
            subscriber = Subscriber.objects.select_for_update().get(
                canonical_email__iexact=canonical
            )
        else:
            _confirmation_event(subscriber, now)
            return subscriber

    if subscriber.status in {Subscriber.Status.ACTIVE, Subscriber.Status.SUPPRESSED}:
        return subscriber

    cooldown = timedelta(seconds=settings.SUBSCRIPTION_CONFIRMATION_COOLDOWN_SECONDS)
    if (
        subscriber.status == Subscriber.Status.PENDING
        and subscriber.confirmation_sent_at is not None
        and now - subscriber.confirmation_sent_at < cooldown
    ):
        return subscriber

    subscriber.email = source
    subscriber.status = Subscriber.Status.PENDING
    subscriber.confirmation_token_version += 1
    subscriber.confirmation_sent_at = now
    subscriber.confirmed_at = None
    subscriber.unsubscribed_at = None
    subscriber.suppressed_at = None
    subscriber.suppression_reason = ""
    subscriber.save(
        update_fields=(
            "email",
            "canonical_email",
            "status",
            "confirmation_token_version",
            "confirmation_sent_at",
            "confirmed_at",
            "unsubscribed_at",
            "suppressed_at",
            "suppression_reason",
        )
    )
    _confirmation_event(subscriber, now)
    return subscriber


@transaction.atomic
def confirm_subscription(credential, *, at=None):
    parsed = read_credential(credential, purpose="confirm")
    try:
        subscriber = Subscriber.objects.select_for_update().get(pk=parsed.subscriber_id)
    except (Subscriber.DoesNotExist, ValidationError, ValueError):
        raise InvalidSubscriptionCredential from None
    if subscriber.confirmation_token_version != parsed.token_version or subscriber.status in {
        Subscriber.Status.UNSUBSCRIBED,
        Subscriber.Status.SUPPRESSED,
    }:
        raise InvalidSubscriptionCredential
    if subscriber.status == Subscriber.Status.ACTIVE:
        return subscriber, False

    now = at or timezone.now()
    subscriber.status = Subscriber.Status.ACTIVE
    subscriber.confirmed_at = now
    subscriber.unsubscribed_at = None
    subscriber.unsubscribe_token_version += 1
    subscriber.save(
        update_fields=(
            "status",
            "confirmed_at",
            "unsubscribed_at",
            "unsubscribe_token_version",
        )
    )
    return subscriber, True


def _skip_unsent_deliveries(subscriber):
    EmailDelivery.objects.filter(
        subscriber=subscriber,
        status__in=(
            EmailDelivery.Status.PENDING,
            EmailDelivery.Status.PROCESSING,
        ),
    ).update(
        status=EmailDelivery.Status.SKIPPED,
        processing_at=None,
        last_error="",
    )


@transaction.atomic
def unsubscribe_with_credential(credential, *, at=None):
    parsed = read_credential(credential, purpose="unsubscribe")
    try:
        subscriber = Subscriber.objects.select_for_update().get(pk=parsed.subscriber_id)
    except (Subscriber.DoesNotExist, ValidationError, ValueError):
        raise InvalidSubscriptionCredential from None
    if subscriber.unsubscribe_token_version != parsed.token_version:
        raise InvalidSubscriptionCredential
    if subscriber.status in {
        Subscriber.Status.UNSUBSCRIBED,
        Subscriber.Status.SUPPRESSED,
    }:
        return subscriber, False

    subscriber.status = Subscriber.Status.UNSUBSCRIBED
    subscriber.unsubscribed_at = at or timezone.now()
    subscriber.suppressed_at = None
    subscriber.suppression_reason = ""
    subscriber.save(
        update_fields=(
            "status",
            "unsubscribed_at",
            "suppressed_at",
            "suppression_reason",
        )
    )
    _skip_unsent_deliveries(subscriber)
    return subscriber, True


@transaction.atomic
def administratively_unsubscribe(subscriber_id, *, at=None):
    subscriber = Subscriber.objects.select_for_update().get(pk=subscriber_id)
    if subscriber.status != Subscriber.Status.SUPPRESSED:
        subscriber.status = Subscriber.Status.UNSUBSCRIBED
        subscriber.unsubscribed_at = at or timezone.now()
        subscriber.suppressed_at = None
        subscriber.suppression_reason = ""
        subscriber.save(
            update_fields=(
                "status",
                "unsubscribed_at",
                "suppressed_at",
                "suppression_reason",
            )
        )
    _skip_unsent_deliveries(subscriber)
    return subscriber


@transaction.atomic
def suppress_subscriber(subscriber_id, *, reason, at=None):
    subscriber = Subscriber.objects.select_for_update().get(pk=subscriber_id)
    if subscriber.status != Subscriber.Status.SUPPRESSED:
        subscriber.status = Subscriber.Status.SUPPRESSED
        subscriber.unsubscribed_at = None
        subscriber.suppressed_at = at or timezone.now()
    subscriber.suppression_reason = (reason or "administrative")[:120]
    subscriber.save(
        update_fields=(
            "status",
            "unsubscribed_at",
            "suppressed_at",
            "suppression_reason",
        )
    )
    _skip_unsent_deliveries(subscriber)
    return subscriber


@transaction.atomic
def unsuppress_subscriber(subscriber_id, *, at=None):
    subscriber = Subscriber.objects.select_for_update().get(pk=subscriber_id)
    if subscriber.status == Subscriber.Status.SUPPRESSED:
        subscriber.status = Subscriber.Status.UNSUBSCRIBED
        subscriber.unsubscribed_at = at or timezone.now()
        subscriber.suppressed_at = None
        subscriber.suppression_reason = ""
        subscriber.unsubscribe_token_version += 1
        subscriber.save(
            update_fields=(
                "status",
                "unsubscribed_at",
                "suppressed_at",
                "suppression_reason",
                "unsubscribe_token_version",
            )
        )
    return subscriber
