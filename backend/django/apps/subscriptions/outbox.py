from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.blog.services.visibility import public_blog_posts
from apps.subscriptions.messages import message_for_delivery
from apps.subscriptions.models import EmailDelivery, EmailOutbox, Subscriber
from apps.subscriptions.providers.base import EmailProviderError


def create_publication_outbox_event(post, *, at=None):
    cutoff = at or timezone.now()
    if not public_blog_posts(at=cutoff).filter(pk=post.pk).exists():
        return None
    event, _ = EmailOutbox.objects.get_or_create(
        post=post,
        message_type=EmailOutbox.MessageType.PUBLICATION,
        defaults={
            "audience_cutoff": cutoff,
            "available_at": cutoff,
            "idempotency_key": f"publication/{post.pk}",
        },
    )
    return event


def _select_for_update_skip_locked(queryset):
    if connection.features.has_select_for_update_skip_locked:
        return queryset.select_for_update(skip_locked=True)
    return queryset.select_for_update()


def claim_outbox_batch(*, limit, at=None):
    now = at or timezone.now()
    stale_before = now - timedelta(seconds=settings.EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS)
    with transaction.atomic():
        queryset = EmailOutbox.objects.filter(
            Q(status=EmailOutbox.Status.PENDING, available_at__lte=now)
            | Q(
                status=EmailOutbox.Status.PROCESSING,
                processing_at__lte=stale_before,
            )
        ).order_by("available_at", "created_at", "id")
        events = list(_select_for_update_skip_locked(queryset)[:limit])
        for event in events:
            event.status = EmailOutbox.Status.PROCESSING
            event.processing_at = now
            event.attempt_count += 1
            event.last_error = ""
            event.save(
                update_fields=(
                    "status",
                    "processing_at",
                    "attempt_count",
                    "last_error",
                )
            )
    return [event.pk for event in events]


def _delivery_status_for_subscriber(event, subscriber):
    if event.message_type == EmailOutbox.MessageType.CONFIRMATION:
        eligible = (
            subscriber.status == Subscriber.Status.PENDING
            and subscriber.confirmation_token_version == event.credential_version
        )
    else:
        eligible = (
            subscriber.status == Subscriber.Status.ACTIVE
            and subscriber.confirmed_at is not None
            and subscriber.confirmed_at <= event.audience_cutoff
        )
    return EmailDelivery.Status.PENDING if eligible else EmailDelivery.Status.SKIPPED


def _create_delivery(event, subscriber, now):
    return EmailDelivery.objects.get_or_create(
        outbox=event,
        subscriber=subscriber,
        defaults={
            "status": _delivery_status_for_subscriber(event, subscriber),
            "available_at": now,
        },
    )


def build_delivery_batch(event_id, *, limit, at=None):
    now = at or timezone.now()
    with transaction.atomic():
        event = (
            EmailOutbox.objects.select_for_update().select_related("subscriber").get(pk=event_id)
        )
        if event.status != EmailOutbox.Status.PROCESSING:
            return []
        if event.message_type == EmailOutbox.MessageType.CONFIRMATION:
            delivery, _ = _create_delivery(event, event.subscriber, now)
            return [delivery.pk]

        delivered_subscribers = EmailDelivery.objects.filter(outbox=event).values("subscriber_id")
        subscribers = list(
            Subscriber.objects.filter(
                confirmed_at__isnull=False,
                confirmed_at__lte=event.audience_cutoff,
            )
            .exclude(pk__in=delivered_subscribers)
            .order_by("confirmed_at", "id")[:limit]
        )
        EmailDelivery.objects.bulk_create(
            [
                EmailDelivery(
                    outbox=event,
                    subscriber=subscriber,
                    status=_delivery_status_for_subscriber(event, subscriber),
                    available_at=now,
                )
                for subscriber in subscribers
            ],
            ignore_conflicts=True,
        )
        return list(
            EmailDelivery.objects.filter(
                outbox=event,
                subscriber_id__in=[subscriber.pk for subscriber in subscribers],
            ).values_list("pk", flat=True)
        )


def _delivery_is_current(delivery):
    event = delivery.outbox
    subscriber = delivery.subscriber
    if event.message_type == EmailOutbox.MessageType.CONFIRMATION:
        return (
            subscriber.status == Subscriber.Status.PENDING
            and subscriber.confirmation_token_version == event.credential_version
        )
    return (
        subscriber.status == Subscriber.Status.ACTIVE
        and subscriber.confirmed_at is not None
        and subscriber.confirmed_at <= event.audience_cutoff
    )


def _claim_delivery(delivery_id, *, at=None):
    now = at or timezone.now()
    stale_before = now - timedelta(seconds=settings.EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS)
    with transaction.atomic():
        delivery = (
            EmailDelivery.objects.select_for_update()
            .select_related("subscriber", "outbox", "outbox__post")
            .get(pk=delivery_id)
        )
        claimable = (
            delivery.status == EmailDelivery.Status.PENDING and delivery.available_at <= now
        ) or (
            delivery.status == EmailDelivery.Status.PROCESSING
            and delivery.processing_at is not None
            and delivery.processing_at <= stale_before
        )
        if not claimable:
            return None
        if (
            delivery.status == EmailDelivery.Status.PROCESSING
            and delivery.processing_at is not None
            and delivery.processing_at
            <= now - timedelta(seconds=settings.EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS)
        ):
            delivery.status = EmailDelivery.Status.FAILED
            delivery.processing_at = None
            delivery.last_error = (
                "Ambiguous provider attempt exceeded the idempotency safety window"
            )
            delivery.save(
                update_fields=(
                    "status",
                    "processing_at",
                    "last_error",
                    "updated_at",
                )
            )
            return None
        if not _delivery_is_current(delivery):
            delivery.status = EmailDelivery.Status.SKIPPED
            delivery.processing_at = None
            delivery.last_error = ""
            delivery.save(update_fields=("status", "processing_at", "last_error", "updated_at"))
            return None
        delivery.status = EmailDelivery.Status.PROCESSING
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
        return delivery


def _retry_delay(attempt_count):
    exponent = min(attempt_count - 1, 20)
    return min(
        settings.EMAIL_OUTBOX_RETRY_MAX_SECONDS,
        settings.EMAIL_OUTBOX_RETRY_BASE_SECONDS * (2**exponent),
    )


def _mark_delivery_failure(delivery, error, *, at=None):
    now = at or timezone.now()
    terminal = not error.retryable or delivery.attempt_count >= settings.EMAIL_OUTBOX_MAX_ATTEMPTS
    updates = {
        "status": (EmailDelivery.Status.FAILED if terminal else EmailDelivery.Status.PENDING),
        "processing_at": None,
        "last_error": error.safe_message[:500],
    }
    if not terminal:
        updates["available_at"] = now + timedelta(seconds=_retry_delay(delivery.attempt_count))
    EmailDelivery.objects.filter(pk=delivery.pk).update(**updates)


def process_delivery(delivery_id, *, provider, at=None):
    delivery = _claim_delivery(delivery_id, at=at)
    if delivery is None:
        return False

    # The claim transaction has committed. No provider I/O occurs while a
    # database transaction or a Wagtail publication transaction is open.
    current = EmailDelivery.objects.select_related("subscriber", "outbox", "outbox__post").get(
        pk=delivery.pk
    )
    if current.status != EmailDelivery.Status.PROCESSING or not _delivery_is_current(current):
        EmailDelivery.objects.filter(
            pk=current.pk,
            status=EmailDelivery.Status.PROCESSING,
        ).update(
            status=EmailDelivery.Status.SKIPPED,
            processing_at=None,
            last_error="",
        )
        return False

    try:
        result = provider.send(
            message_for_delivery(current),
            current.provider_idempotency_key,
        )
    except EmailProviderError as error:
        _mark_delivery_failure(current, error, at=at)
        return False
    except Exception as error:  # pragma: no cover - defensive provider boundary
        _mark_delivery_failure(
            current,
            EmailProviderError(
                f"Email provider failure ({type(error).__name__})",
                retryable=True,
            ),
            at=at,
        )
        return False

    now = at or timezone.now()
    EmailDelivery.objects.filter(pk=current.pk).update(
        status=EmailDelivery.Status.SENT,
        processing_at=None,
        provider_message_id=result.message_id,
        provider_created_at=result.created_at,
        sent_at=now,
        last_error="",
    )
    return True


def _has_missing_publication_audience(event):
    delivered_subscribers = EmailDelivery.objects.filter(outbox=event).values("subscriber_id")
    return (
        Subscriber.objects.filter(
            confirmed_at__isnull=False,
            confirmed_at__lte=event.audience_cutoff,
        )
        .exclude(pk__in=delivered_subscribers)
        .exists()
    )


def finalize_outbox_event(event_id, *, at=None):
    now = at or timezone.now()
    with transaction.atomic():
        event = EmailOutbox.objects.select_for_update().get(pk=event_id)
        if event.status != EmailOutbox.Status.PROCESSING:
            return event.status
        if (
            event.message_type == EmailOutbox.MessageType.PUBLICATION
            and _has_missing_publication_audience(event)
        ):
            event.status = EmailOutbox.Status.PENDING
            event.processing_at = None
            event.available_at = now
            event.save(update_fields=("status", "processing_at", "available_at"))
            return event.status

        deliveries = EmailDelivery.objects.filter(outbox=event)
        incomplete = deliveries.filter(
            status__in=(
                EmailDelivery.Status.PENDING,
                EmailDelivery.Status.PROCESSING,
            )
        )
        if incomplete.exists():
            next_available = (
                incomplete.filter(status=EmailDelivery.Status.PENDING)
                .order_by("available_at")
                .values_list("available_at", flat=True)
                .first()
                or now
            )
            event.status = EmailOutbox.Status.PENDING
            event.processing_at = None
            event.available_at = next_available
            event.save(update_fields=("status", "processing_at", "available_at"))
            return event.status
        if deliveries.filter(status=EmailDelivery.Status.FAILED).exists():
            event.status = EmailOutbox.Status.FAILED
            event.processing_at = None
            event.last_error = "One or more deliveries reached the retry limit"
            event.save(update_fields=("status", "processing_at", "last_error"))
            return event.status

        event.status = EmailOutbox.Status.DELIVERED
        event.processing_at = None
        event.delivered_at = now
        event.last_error = ""
        event.save(
            update_fields=(
                "status",
                "processing_at",
                "delivered_at",
                "last_error",
            )
        )
        return event.status


def process_outbox_event(event_id, *, provider, delivery_limit=None, at=None):
    limit = delivery_limit or settings.EMAIL_DELIVERY_BATCH_SIZE
    build_delivery_batch(event_id, limit=limit, at=at)
    stale_before = (at or timezone.now()) - timedelta(
        seconds=settings.EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS
    )
    delivery_ids = list(
        EmailDelivery.objects.filter(outbox_id=event_id)
        .filter(
            Q(status=EmailDelivery.Status.PENDING, available_at__lte=at or timezone.now())
            | Q(
                status=EmailDelivery.Status.PROCESSING,
                processing_at__lte=stale_before,
            )
        )
        .order_by("available_at", "created_at", "id")
        .values_list("pk", flat=True)[:limit]
    )
    sent = 0
    for delivery_id in delivery_ids:
        sent += int(process_delivery(delivery_id, provider=provider, at=at))
    status = finalize_outbox_event(event_id, at=at)
    return sent, status
