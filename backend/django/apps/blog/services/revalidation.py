import hashlib
import hmac
import json
import urllib.error
import urllib.request
from datetime import UTC, timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models, transaction
from django.utils import timezone

from apps.blog.models import RevalidationEvent

SIGNATURE_VERSION = "v1"


def _isoformat_utc(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def event_payload(event):
    payload = {
        "action": event.action,
        "event_id": str(event.pk),
        "occurred_at": _isoformat_utc(event.occurred_at),
        "page_id": event.page_id,
        "slug": event.slug,
    }
    if event.previous_slug:
        payload["previous_slug"] = event.previous_slug
    return payload


def encode_event_body(event):
    return json.dumps(
        event_payload(event),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def sign_revalidation_body(body, timestamp, secret=None):
    signing_secret = settings.REVALIDATION_SECRET if secret is None else secret
    if len(signing_secret.encode()) < 32:
        raise ImproperlyConfigured("REVALIDATION_SECRET must be at least 32 bytes")
    message = str(timestamp).encode() + b"." + body
    digest = hmac.new(signing_secret.encode(), message, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"


def create_revalidation_event(page, *, action=None):
    previous_event = (
        RevalidationEvent.objects.filter(page_id=page.pk).order_by("-created_at", "-pk").first()
    )
    if action is None:
        if previous_event is None or previous_event.action in {
            RevalidationEvent.Action.UNPUBLISHED,
            RevalidationEvent.Action.EXPIRED,
        }:
            action = RevalidationEvent.Action.PUBLISHED
        else:
            action = RevalidationEvent.Action.UPDATED

    previous_slug = ""
    if (
        previous_event is not None
        and previous_event.slug != page.slug
        and action
        in {
            RevalidationEvent.Action.PUBLISHED,
            RevalidationEvent.Action.UPDATED,
        }
    ):
        previous_slug = previous_event.slug

    return RevalidationEvent.objects.create(
        action=action,
        page_id=page.pk,
        slug=page.slug,
        previous_slug=previous_slug,
        occurred_at=timezone.now(),
    )


def deliver_event_after_commit(event_id):
    if not settings.REVALIDATION_URL:
        return

    transaction.on_commit(lambda: deliver_event(event_id))


def _claim_event(event_id):
    stale_before = timezone.now() - timedelta(
        seconds=settings.REVALIDATION_PROCESSING_TIMEOUT_SECONDS
    )
    with transaction.atomic():
        event = RevalidationEvent.objects.select_for_update().get(pk=event_id)
        if event.state == RevalidationEvent.State.DELIVERED:
            return None
        if (
            event.state == RevalidationEvent.State.PROCESSING
            and event.last_attempt_at
            and event.last_attempt_at > stale_before
        ):
            return None

        event.state = RevalidationEvent.State.PROCESSING
        event.attempt_count += 1
        event.last_attempt_at = timezone.now()
        event.last_error = ""
        event.save(
            update_fields=[
                "state",
                "attempt_count",
                "last_attempt_at",
                "last_error",
            ]
        )
        return event


def _mark_delivered(event_id):
    RevalidationEvent.objects.filter(pk=event_id).update(
        state=RevalidationEvent.State.DELIVERED,
        delivered_at=timezone.now(),
        last_error="",
    )


def _mark_failed(event_id, error):
    RevalidationEvent.objects.filter(pk=event_id).update(
        state=RevalidationEvent.State.PENDING,
        delivered_at=None,
        last_error=error[:500],
    )


def deliver_event(event_id, *, opener=None):
    event = _claim_event(event_id)
    if event is None:
        return False

    if not settings.REVALIDATION_URL or not settings.REVALIDATION_SECRET:
        _mark_failed(event.pk, "Revalidation delivery is not configured")
        return False

    body = encode_event_body(event)
    timestamp = int(timezone.now().timestamp())
    request = urllib.request.Request(
        settings.REVALIDATION_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Revalidation-Timestamp": str(timestamp),
            "X-Revalidation-Signature": sign_revalidation_body(body, timestamp),
        },
    )
    open_request = opener or urllib.request.urlopen

    try:
        response = open_request(request, timeout=settings.REVALIDATION_TIMEOUT_SECONDS)
        status = getattr(response, "status", response.getcode())
        if not 200 <= status < 300:
            _mark_failed(event.pk, f"HTTP {status}")
            return False
    except urllib.error.HTTPError as error:
        _mark_failed(event.pk, f"HTTP {error.code}")
        return False
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        _mark_failed(event.pk, f"Network failure ({type(error).__name__})")
        return False
    except Exception as error:  # pragma: no cover - defensive adapter boundary
        _mark_failed(event.pk, f"Delivery failure ({type(error).__name__})")
        return False

    _mark_delivered(event.pk)
    return True


def pending_event_ids(*, limit):
    stale_before = timezone.now() - timedelta(
        seconds=settings.REVALIDATION_PROCESSING_TIMEOUT_SECONDS
    )
    return list(
        RevalidationEvent.objects.filter(
            models.Q(state=RevalidationEvent.State.PENDING)
            | models.Q(
                state=RevalidationEvent.State.PROCESSING,
                last_attempt_at__lte=stale_before,
            )
        )
        .order_by("created_at", "pk")
        .values_list("pk", flat=True)[:limit]
    )
