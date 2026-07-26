import hashlib
import hmac
import io
import json
import urllib.error
from datetime import timedelta

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.blog.models import BlogPostPage, RevalidationEvent
from apps.blog.services.revalidation import (
    deliver_event,
    encode_event_body,
    event_payload,
    sign_revalidation_body,
)

pytestmark = pytest.mark.django_db
REVALIDATION_SECRET = "s" * 32


class SuccessfulResponse:
    status = 200

    def getcode(self):
        return self.status


def publish(page):
    page.save_revision().publish()
    return BlogPostPage.objects.get(pk=page.pk)


def test_publish_update_slug_change_and_unpublish_create_durable_events(blog_post):
    blog_post.slug = "привет-мир"
    published = publish(blog_post)
    first = RevalidationEvent.objects.get()
    assert first.action == RevalidationEvent.Action.PUBLISHED
    assert first.page_id == published.pk
    assert first.slug == "привет-мир"
    assert first.state == RevalidationEvent.State.PENDING
    assert first.attempt_count == 0

    published.slug = "новый-мир"
    published.title = "Updated"
    published = publish(published)
    second = RevalidationEvent.objects.order_by("created_at", "pk").last()
    assert second.action == RevalidationEvent.Action.UPDATED
    assert second.slug == "новый-мир"
    assert second.previous_slug == "привет-мир"

    published.unpublish()
    third = RevalidationEvent.objects.order_by("created_at", "pk").last()
    assert third.action == RevalidationEvent.Action.UNPUBLISHED
    assert third.slug == "новый-мир"

    assert json.loads(encode_event_body(second))["previous_slug"] == "привет-мир"


def test_scheduled_publication_and_expiry_create_events(blog_post):
    go_live_at = timezone.now() - timedelta(minutes=1)
    blog_post.go_live_at = go_live_at
    blog_post.save_revision(approved_go_live_at=go_live_at)
    call_command("publish_scheduled_pages", verbosity=0)

    assert RevalidationEvent.objects.get().action == RevalidationEvent.Action.PUBLISHED

    BlogPostPage.objects.filter(pk=blog_post.pk).update(
        expire_at=timezone.now() - timedelta(minutes=1)
    )
    call_command("publish_scheduled_pages", verbosity=0)

    assert list(RevalidationEvent.objects.values_list("action", flat=True)) == [
        RevalidationEvent.Action.PUBLISHED,
        RevalidationEvent.Action.EXPIRED,
    ]


def test_hmac_signature_covers_timestamp_and_exact_raw_body(blog_post):
    publish(blog_post)
    event = RevalidationEvent.objects.get()
    body = encode_event_body(event)
    timestamp = 1_800_000_000

    signature = sign_revalidation_body(body, timestamp, secret=REVALIDATION_SECRET)
    expected = hmac.new(
        REVALIDATION_SECRET.encode(),
        str(timestamp).encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()

    assert signature == f"v1={expected}"
    assert json.loads(body) == event_payload(event)
    assert set(json.loads(body)) == {
        "event_id",
        "action",
        "page_id",
        "slug",
        "occurred_at",
    }


def test_runtime_rejects_short_revalidation_secret():
    with pytest.raises(
        ImproperlyConfigured,
        match="REVALIDATION_SECRET must be at least 32 bytes",
    ):
        sign_revalidation_body(b"{}", 1_800_000_000, secret="short")


@override_settings(
    REVALIDATION_URL="http://frontend.test/api/revalidate",
    REVALIDATION_SECRET=REVALIDATION_SECRET,
)
def test_delivery_success_signs_request_and_marks_delivered(blog_post):
    publish(blog_post)
    event = RevalidationEvent.objects.get()
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return SuccessfulResponse()

    assert deliver_event(event.pk, opener=opener) is True
    event.refresh_from_db()
    assert event.state == RevalidationEvent.State.DELIVERED
    assert event.attempt_count == 1
    assert event.delivered_at is not None
    assert event.last_error == ""
    assert captured["request"].method == "POST"
    assert captured["request"].data == encode_event_body(event)
    timestamp = captured["request"].headers["X-revalidation-timestamp"]
    assert captured["request"].headers["X-revalidation-signature"] == sign_revalidation_body(
        captured["request"].data,
        timestamp,
    )


@override_settings(
    REVALIDATION_URL="http://frontend.test/api/revalidate",
    REVALIDATION_SECRET=REVALIDATION_SECRET,
)
def test_network_failure_is_pending_and_retry_succeeds(blog_post):
    publish(blog_post)
    event = RevalidationEvent.objects.get()

    def failing_opener(request, timeout):
        raise urllib.error.URLError("secret-bearing upstream text must not persist")

    assert deliver_event(event.pk, opener=failing_opener) is False
    event.refresh_from_db()
    assert event.state == RevalidationEvent.State.PENDING
    assert event.attempt_count == 1
    assert event.last_error == "Network failure (URLError)"
    assert "secret-bearing" not in event.last_error

    assert deliver_event(event.pk, opener=lambda request, timeout: SuccessfulResponse()) is True
    event.refresh_from_db()
    assert event.state == RevalidationEvent.State.DELIVERED
    assert event.attempt_count == 2


@override_settings(
    REVALIDATION_URL="http://frontend.test/api/revalidate",
    REVALIDATION_SECRET=REVALIDATION_SECRET,
)
def test_non_2xx_failure_is_retained(blog_post):
    publish(blog_post)
    event = RevalidationEvent.objects.get()

    def opener(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            503,
            "response body must not persist",
            {},
            io.BytesIO(b"possibly sensitive response"),
        )

    assert deliver_event(event.pk, opener=opener) is False
    event.refresh_from_db()
    assert event.state == RevalidationEvent.State.PENDING
    assert event.last_error == "HTTP 503"


@override_settings(
    REVALIDATION_URL="http://frontend.test/api/revalidate",
    REVALIDATION_SECRET=REVALIDATION_SECRET,
)
def test_duplicate_delivery_is_idempotent(blog_post):
    publish(blog_post)
    event = RevalidationEvent.objects.get()
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return SuccessfulResponse()

    assert deliver_event(event.pk, opener=opener) is True
    assert deliver_event(event.pk, opener=opener) is False
    event.refresh_from_db()
    assert calls == 1
    assert event.attempt_count == 1


@override_settings(
    REVALIDATION_URL="http://frontend.test/api/revalidate",
    REVALIDATION_SECRET=REVALIDATION_SECRET,
)
def test_management_command_processes_pending_events(blog_post, monkeypatch):
    publish(blog_post)
    calls = []

    def fake_deliver(event_id):
        calls.append(event_id)
        return True

    monkeypatch.setattr(
        "apps.blog.management.commands.process_revalidation_outbox.deliver_event",
        fake_deliver,
    )
    output = io.StringIO()

    call_command("process_revalidation_outbox", limit=10, stdout=output)

    assert calls == [RevalidationEvent.objects.get().pk]
    assert "1 delivered" in output.getvalue()


def test_outbox_failure_rolls_back_publication_state(blog_post, monkeypatch):
    def fail_event_creation(page, action=None):
        raise RuntimeError("simulated outbox write failure")

    monkeypatch.setattr("apps.blog.signals.create_revalidation_event", fail_event_creation)

    with pytest.raises(RuntimeError, match="outbox write failure"):
        blog_post.save_revision().publish()

    blog_post.refresh_from_db()
    assert blog_post.live is False
    assert RevalidationEvent.objects.count() == 0


def test_outbox_failure_rolls_back_unpublish_state(blog_post, monkeypatch):
    published = publish(blog_post)

    def fail_event_creation(page, action=None):
        raise RuntimeError("simulated outbox write failure")

    monkeypatch.setattr("apps.blog.signals.create_revalidation_event", fail_event_creation)

    with pytest.raises(RuntimeError, match="outbox write failure"):
        published.unpublish()

    published.refresh_from_db()
    assert published.live is True
    assert RevalidationEvent.objects.count() == 1
