import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.subscriptions.models import EmailDelivery, EmailWebhookEvent
from apps.subscriptions.services import suppress_subscriber

RECOGNIZED_DELIVERY_EVENTS = frozenset(
    {
        "email.delivered",
        "email.bounced",
        "email.complained",
    }
)


def normalized_bounce_type(data):
    bounce = data.get("bounce") if isinstance(data.get("bounce"), dict) else {}
    value = bounce.get("type") or bounce.get("subType") or "permanent"
    if not isinstance(value, str):
        return "permanent"
    normalized = re.sub(r"[^a-z0-9_-]+", "_", value.casefold()).strip("_")
    return normalized[:64] or "permanent"


def webhook_event_defaults(*, event_type, provider_message_id, occurred_at, bounce_type, at):
    recognized = event_type in RECOGNIZED_DELIVERY_EVENTS and provider_message_id is not None
    if recognized:
        return {
            "event_type": event_type,
            "provider_message_id": provider_message_id,
            "provider_occurred_at": occurred_at,
            "bounce_type": bounce_type,
            "processing_state": EmailWebhookEvent.ProcessingState.PENDING,
            "expires_at": at + timedelta(seconds=settings.EMAIL_WEBHOOK_CORRELATION_TTL_SECONDS),
        }
    return {
        "event_type": event_type,
        "provider_message_id": None,
        "provider_occurred_at": occurred_at,
        "bounce_type": "",
        "processing_state": EmailWebhookEvent.ProcessingState.IGNORED,
        "expires_at": at + timedelta(seconds=settings.EMAIL_WEBHOOK_RETENTION_SECONDS),
        "applied_at": at,
    }


def _apply_delivery_event(delivery, event, now):
    if event.event_type == "email.delivered":
        if delivery.status not in {
            EmailDelivery.Status.BOUNCED,
            EmailDelivery.Status.COMPLAINED,
        }:
            delivery.status = EmailDelivery.Status.DELIVERED
            delivery.delivered_at = event.provider_occurred_at or now
            delivery.save(update_fields=("status", "delivered_at", "updated_at"))
        return
    if event.event_type == "email.bounced":
        if delivery.status != EmailDelivery.Status.COMPLAINED:
            delivery.status = EmailDelivery.Status.BOUNCED
            delivery.bounced_at = event.provider_occurred_at or now
            delivery.bounce_type = event.bounce_type or "permanent"
            delivery.save(update_fields=("status", "bounced_at", "bounce_type", "updated_at"))
            suppress_subscriber(delivery.subscriber_id, reason="hard_bounce")
        return
    if event.event_type == "email.complained":
        delivery.status = EmailDelivery.Status.COMPLAINED
        delivery.complained_at = event.provider_occurred_at or now
        delivery.save(update_fields=("status", "complained_at", "updated_at"))
        suppress_subscriber(delivery.subscriber_id, reason="complaint")


def reconcile_pending_webhooks(*, provider_message_id=None, limit=None, at=None):
    now = at or timezone.now()
    batch_size = limit or settings.EMAIL_WEBHOOK_RECONCILIATION_BATCH_SIZE
    applied = 0
    with transaction.atomic():
        events = EmailWebhookEvent.objects.select_for_update().filter(
            processing_state=EmailWebhookEvent.ProcessingState.PENDING,
            expires_at__gt=now,
        )
        if provider_message_id is not None:
            events = events.filter(provider_message_id=provider_message_id)
        else:
            events = events.filter(
                provider_message_id__in=EmailDelivery.objects.exclude(
                    provider_message_id__isnull=True
                ).values("provider_message_id")
            )
        events = list(
            events.order_by(
                F("provider_occurred_at").asc(nulls_last=True),
                "processed_at",
                "id",
            )[:batch_size]
        )
        for event in events:
            delivery = (
                EmailDelivery.objects.select_for_update()
                .filter(provider_message_id=event.provider_message_id)
                .first()
            )
            if delivery is None:
                continue
            _apply_delivery_event(delivery, event, now)
            event.delivery = delivery
            event.processing_state = EmailWebhookEvent.ProcessingState.APPLIED
            event.applied_at = now
            event.expires_at = event.processed_at + timedelta(
                seconds=settings.EMAIL_WEBHOOK_RETENTION_SECONDS
            )
            event.save(
                update_fields=(
                    "delivery",
                    "processing_state",
                    "applied_at",
                    "expires_at",
                )
            )
            applied += 1
    return applied


def expire_unmatched_webhooks(*, limit, at=None):
    now = at or timezone.now()
    with transaction.atomic():
        events = list(
            EmailWebhookEvent.objects.select_for_update()
            .filter(
                processing_state=EmailWebhookEvent.ProcessingState.PENDING,
                expires_at__lte=now,
            )
            .order_by("expires_at", "id")[:limit]
        )
        for event in events:
            event.processing_state = EmailWebhookEvent.ProcessingState.IGNORED
            event.applied_at = now
            event.expires_at = now + timedelta(seconds=settings.EMAIL_WEBHOOK_RETENTION_SECONDS)
            event.save(update_fields=("processing_state", "applied_at", "expires_at"))
    return len(events)


def delete_expired_webhook_history(*, limit, at=None):
    now = at or timezone.now()
    event_ids = list(
        EmailWebhookEvent.objects.filter(
            processing_state__in=(
                EmailWebhookEvent.ProcessingState.APPLIED,
                EmailWebhookEvent.ProcessingState.IGNORED,
            ),
            expires_at__lte=now,
        )
        .order_by("expires_at", "id")
        .values_list("pk", flat=True)[:limit]
    )
    if event_ids:
        EmailWebhookEvent.objects.filter(pk__in=event_ids).delete()
    return len(event_ids)
