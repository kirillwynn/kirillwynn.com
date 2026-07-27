import hashlib
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.blog.services.visibility import public_blog_posts
from apps.subscriptions.message_limits import (
    MAX_EMAIL_SUBJECT_LENGTH,
    MAX_PUBLIC_ORIGIN_LENGTH,
    MAX_PUBLICATION_EXCERPT_LENGTH,
    MAX_PUBLICATION_TITLE_LENGTH,
    MAX_SNAPSHOT_URL_LENGTH,
    bounded_snapshot_value,
)
from apps.subscriptions.messages import MESSAGE_SCHEMA_VERSION, message_for_delivery
from apps.subscriptions.models import EmailDelivery, EmailOutbox, Subscriber
from apps.subscriptions.providers.base import EmailProviderError
from config.email_settings import normalize_email_from_address


def _common_snapshot():
    return {
        "message_schema_version": MESSAGE_SCHEMA_VERSION,
        "snapshot_from_email": normalize_email_from_address(settings.EMAIL_FROM_ADDRESS),
        "snapshot_site_url": bounded_snapshot_value(
            settings.PUBLIC_SITE_URL.rstrip("/"),
            name="PUBLIC_SITE_URL",
            max_length=MAX_PUBLIC_ORIGIN_LENGTH,
        ),
    }


def confirmation_outbox_snapshot():
    subject = "Confirm your subscription to Kirill Wynn"
    return {
        **_common_snapshot(),
        "snapshot_subject": bounded_snapshot_value(
            subject,
            name="confirmation subject",
            max_length=MAX_EMAIL_SUBJECT_LENGTH,
        ),
        "snapshot_post_title": "",
        "snapshot_post_excerpt": "",
        "snapshot_post_url": "",
    }


def publication_outbox_snapshot(post):
    title = bounded_snapshot_value(
        post.title,
        name="publication title",
        max_length=MAX_PUBLICATION_TITLE_LENGTH,
    )
    excerpt = bounded_snapshot_value(
        post.excerpt,
        name="publication excerpt",
        max_length=MAX_PUBLICATION_EXCERPT_LENGTH,
    )
    return {
        **_common_snapshot(),
        "snapshot_subject": bounded_snapshot_value(
            f"New post: {title}",
            name="publication subject",
            max_length=MAX_EMAIL_SUBJECT_LENGTH,
        ),
        "snapshot_post_title": title,
        "snapshot_post_excerpt": excerpt,
        "snapshot_post_url": bounded_snapshot_value(
            post.resolved_canonical_url,
            name="publication URL",
            max_length=MAX_SNAPSHOT_URL_LENGTH,
        ),
    }


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
            **publication_outbox_snapshot(post),
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


def _create_delivery(event, subscriber, now, provider):
    existing = EmailDelivery.objects.filter(outbox=event, subscriber=subscriber).first()
    if existing is not None:
        return existing, False
    delivery = _new_delivery(event, subscriber, now, provider)
    try:
        with transaction.atomic():
            delivery.save(force_insert=True)
    except IntegrityError:
        return EmailDelivery.objects.get(outbox=event, subscriber=subscriber), False
    return delivery, True


def _new_delivery(event, subscriber, now, provider):
    credential_version = (
        event.credential_version
        if event.message_type == EmailOutbox.MessageType.CONFIRMATION
        else subscriber.unsubscribe_token_version
    )
    delivery = EmailDelivery(
        outbox=event,
        subscriber=subscriber,
        status=_delivery_status_for_subscriber(event, subscriber),
        available_at=now,
        snapshot_recipient_email=subscriber.email,
        snapshot_credential_version=credential_version,
        credential_issued_at=now,
    )
    prepared_request = provider.prepare_request(message_for_delivery(delivery))
    delivery.provider_contract_id = prepared_request.transport.contract_id
    delivery.provider_serializer_version = prepared_request.transport.serializer_version
    delivery.provider_idempotency_namespace = prepared_request.transport.idempotency_namespace
    delivery.provider_payload_hash = _provider_payload_hash(prepared_request.body)
    return delivery


def _provider_payload_hash(body):
    return hashlib.sha256(body).hexdigest()


def build_delivery_batch(event_id, *, limit, at=None, provider=None):
    if provider is None:
        from apps.subscriptions.providers import configured_email_provider

        provider = configured_email_provider()
    now = at or timezone.now()
    with transaction.atomic():
        event = (
            EmailOutbox.objects.select_for_update().select_related("subscriber").get(pk=event_id)
        )
        if event.status != EmailOutbox.Status.PROCESSING:
            return []
        if event.message_type == EmailOutbox.MessageType.CONFIRMATION:
            delivery, _ = _create_delivery(event, event.subscriber, now, provider)
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
            [_new_delivery(event, subscriber, now, provider) for subscriber in subscribers],
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


def _publication_is_public(delivery, now):
    if delivery.outbox.message_type != EmailOutbox.MessageType.PUBLICATION:
        return True
    return public_blog_posts(at=now).filter(pk=delivery.outbox.post_id).exists()


def _safety_deadline(delivery):
    if delivery.first_provider_attempt_at is None:
        return None
    return delivery.first_provider_attempt_at + timedelta(
        seconds=settings.EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS
    )


def _mark_manual_review(delivery, reason, message):
    EmailDelivery.objects.filter(pk=delivery.pk).update(
        status=EmailDelivery.Status.MANUAL_REVIEW,
        processing_at=None,
        ambiguity_reason=reason,
        last_error=message[:500],
        updated_at=timezone.now(),
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
        deadline = _safety_deadline(delivery)
        if deadline is not None and now >= deadline:
            delivery.status = EmailDelivery.Status.MANUAL_REVIEW
            delivery.processing_at = None
            delivery.ambiguity_reason = EmailDelivery.AmbiguityReason.WINDOW_EXPIRED
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
            return None
        if delivery.first_provider_attempt_at is None and not _publication_is_public(delivery, now):
            delivery.status = EmailDelivery.Status.SKIPPED
            delivery.processing_at = None
            delivery.last_error = "Publication is no longer publicly deliverable"
            delivery.save(update_fields=("status", "processing_at", "last_error", "updated_at"))
            return None
        if not _delivery_is_current(delivery):
            if delivery.first_provider_attempt_at is not None:
                delivery.status = EmailDelivery.Status.MANUAL_REVIEW
                delivery.ambiguity_reason = EmailDelivery.AmbiguityReason.IN_FLIGHT_CANCELLED
                delivery.last_error = "Subscriber changed after a possible provider acceptance"
            else:
                delivery.status = EmailDelivery.Status.SKIPPED
                delivery.last_error = ""
            delivery.processing_at = None
            delivery.save(
                update_fields=(
                    "status",
                    "processing_at",
                    "ambiguity_reason",
                    "last_error",
                    "updated_at",
                )
            )
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
    with transaction.atomic():
        current = (
            EmailDelivery.objects.select_for_update()
            .select_related("subscriber")
            .get(pk=delivery.pk)
        )
        if current.status != EmailDelivery.Status.PROCESSING:
            return
        inactive_in_flight = current.subscriber.status != Subscriber.Status.ACTIVE and (
            current.outbox.message_type == EmailOutbox.MessageType.PUBLICATION
        )
        terminal = (
            not error.retryable or current.attempt_count >= settings.EMAIL_OUTBOX_MAX_ATTEMPTS
        )
        if error.ambiguity_reason == EmailDelivery.AmbiguityReason.PAYLOAD_MISMATCH:
            current.status = EmailDelivery.Status.MANUAL_REVIEW
        elif error.retryable and inactive_in_flight:
            current.status = EmailDelivery.Status.MANUAL_REVIEW
            error.ambiguity_reason = EmailDelivery.AmbiguityReason.IN_FLIGHT_CANCELLED
        else:
            current.status = (
                EmailDelivery.Status.FAILED if terminal else EmailDelivery.Status.PENDING
            )
        current.processing_at = None
        current.last_error = error.safe_message[:500]
        current.ambiguity_reason = error.ambiguity_reason
        update_fields = [
            "status",
            "processing_at",
            "last_error",
            "ambiguity_reason",
            "updated_at",
        ]
        if current.status == EmailDelivery.Status.PENDING:
            current.available_at = now + timedelta(seconds=_retry_delay(current.attempt_count))
            update_fields.append("available_at")
        current.save(update_fields=update_fields)


def _prepare_provider_attempt(delivery_id, *, provider, at=None):
    now = at or timezone.now()
    with transaction.atomic():
        delivery = (
            EmailDelivery.objects.select_for_update()
            .select_related("subscriber", "outbox", "outbox__post")
            .get(pk=delivery_id)
        )
        if delivery.status != EmailDelivery.Status.PROCESSING:
            return None
        if not _delivery_is_current(delivery):
            if delivery.first_provider_attempt_at is not None:
                delivery.status = EmailDelivery.Status.MANUAL_REVIEW
                delivery.ambiguity_reason = EmailDelivery.AmbiguityReason.IN_FLIGHT_CANCELLED
                delivery.last_error = "Subscriber changed after a possible provider acceptance"
            else:
                delivery.status = EmailDelivery.Status.SKIPPED
                delivery.last_error = ""
            delivery.processing_at = None
            delivery.save(
                update_fields=(
                    "status",
                    "processing_at",
                    "ambiguity_reason",
                    "last_error",
                    "updated_at",
                )
            )
            return None
        if delivery.first_provider_attempt_at is None and not _publication_is_public(delivery, now):
            delivery.status = EmailDelivery.Status.SKIPPED
            delivery.processing_at = None
            delivery.last_error = "Publication is no longer publicly deliverable"
            delivery.save(update_fields=("status", "processing_at", "last_error", "updated_at"))
            return None
        try:
            message = message_for_delivery(delivery)
            prepared_request = provider.prepare_request(message)
        except (ImproperlyConfigured, TypeError, ValueError):
            _mark_manual_review(
                delivery,
                EmailDelivery.AmbiguityReason.PAYLOAD_MISMATCH,
                "Immutable email message schema cannot be rendered",
            )
            return None
        if prepared_request.transport.contract_id != delivery.provider_contract_id:
            _mark_manual_review(
                delivery,
                EmailDelivery.AmbiguityReason.TRANSPORT_IDENTITY_MISMATCH,
                "Provider transport contract identifier mismatch",
            )
            return None
        if prepared_request.transport.serializer_version != delivery.provider_serializer_version:
            _mark_manual_review(
                delivery,
                EmailDelivery.AmbiguityReason.SERIALIZER_VERSION_MISMATCH,
                "Provider serializer contract version mismatch",
            )
            return None
        if (
            prepared_request.transport.idempotency_namespace
            != delivery.provider_idempotency_namespace
        ):
            _mark_manual_review(
                delivery,
                EmailDelivery.AmbiguityReason.IDEMPOTENCY_NAMESPACE_MISMATCH,
                "Provider idempotency namespace mismatch",
            )
            return None
        payload_hash = _provider_payload_hash(prepared_request.body)
        if payload_hash != delivery.provider_payload_hash:
            _mark_manual_review(
                delivery,
                EmailDelivery.AmbiguityReason.PAYLOAD_MISMATCH,
                "Provider payload fingerprint mismatch",
            )
            return None
        deadline = _safety_deadline(delivery)
        if deadline is not None and now >= deadline:
            _mark_manual_review(
                delivery,
                EmailDelivery.AmbiguityReason.WINDOW_EXPIRED,
                "Provider ambiguity exceeded the idempotency safety window",
            )
            return None
        if delivery.first_provider_attempt_at is None:
            delivery.first_provider_attempt_at = now
        delivery.last_provider_attempt_at = now
        delivery.save(
            update_fields=(
                "first_provider_attempt_at",
                "last_provider_attempt_at",
                "updated_at",
            )
        )
        return delivery, prepared_request


def process_delivery(delivery_id, *, provider, at=None):
    delivery = _claim_delivery(delivery_id, at=at)
    if delivery is None:
        return False

    # The claim transaction has committed. No provider I/O occurs while a
    # database transaction or a Wagtail publication transaction is open.
    prepared = _prepare_provider_attempt(delivery.pk, provider=provider, at=at)
    if prepared is None:
        return False
    current, prepared_request = prepared

    try:
        result = provider.send(
            prepared_request,
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
    with transaction.atomic():
        settling = EmailDelivery.objects.select_for_update().get(pk=current.pk)
        if settling.status != EmailDelivery.Status.PROCESSING:
            return False
        settling.status = EmailDelivery.Status.SENT
        settling.processing_at = None
        settling.provider_message_id = result.message_id
        settling.provider_created_at = result.created_at
        settling.sent_at = now
        settling.last_error = ""
        settling.ambiguity_reason = ""
        settling.save(
            update_fields=(
                "status",
                "processing_at",
                "provider_message_id",
                "provider_created_at",
                "sent_at",
                "last_error",
                "ambiguity_reason",
                "updated_at",
            )
        )
    from apps.subscriptions.webhooks import reconcile_pending_webhooks

    reconcile_pending_webhooks(provider_message_id=result.message_id)
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
        if deliveries.filter(
            status__in=(
                EmailDelivery.Status.FAILED,
                EmailDelivery.Status.MANUAL_REVIEW,
            )
        ).exists():
            event.status = EmailOutbox.Status.FAILED
            event.processing_at = None
            event.last_error = "One or more deliveries require terminal review"
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
    build_delivery_batch(event_id, limit=limit, at=at, provider=provider)
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
