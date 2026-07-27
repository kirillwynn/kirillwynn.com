import io
import json
import urllib.error
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from wagtail.models import PageViewRestriction

from apps.blog.models import BlogPostPage
from apps.subscriptions.models import EmailDelivery, EmailOutbox, Subscriber
from apps.subscriptions.outbox import (
    build_delivery_batch,
    claim_outbox_batch,
    process_outbox_event,
)
from apps.subscriptions.providers.base import (
    EmailProvider,
    EmailProviderError,
    ProviderSendResult,
)
from apps.subscriptions.providers.memory import MemoryEmailProvider
from apps.subscriptions.providers.resend import ResendEmailProvider
from apps.subscriptions.services import request_subscription

pytestmark = pytest.mark.django_db


def publish(page):
    page.save_revision().publish()
    return BlogPostPage.objects.get(pk=page.pk)


def active_subscriber(email, confirmed_at):
    return Subscriber.objects.create(
        email=email,
        status=Subscriber.Status.ACTIVE,
        confirmed_at=confirmed_at,
    )


def publication_event(post):
    return EmailOutbox.objects.get(
        post=post,
        message_type=EmailOutbox.MessageType.PUBLICATION,
    )


def test_publication_event_occurs_once_only_at_first_public_publication(blog_post):
    assert EmailOutbox.objects.count() == 0
    published = publish(blog_post)
    event = publication_event(published)
    cutoff = event.audience_cutoff

    published.title = "Edited title"
    publish(published)

    assert EmailOutbox.objects.filter(message_type=EmailOutbox.MessageType.PUBLICATION).count() == 1
    event.refresh_from_db()
    assert event.audience_cutoff == cutoff


def test_draft_future_and_restricted_posts_do_not_create_publication_events(
    blog_index,
    blog_post,
):
    assert EmailOutbox.objects.count() == 0

    future = BlogPostPage(
        title="Future",
        slug="future",
        excerpt="Future excerpt",
        body=[("rich_text", "<p>Future</p>")],
        live=False,
        go_live_at=timezone.now() + timedelta(hours=1),
    )
    blog_index.add_child(instance=future)
    future.save_revision(approved_go_live_at=future.go_live_at).publish()

    restricted = BlogPostPage(
        title="Restricted",
        slug="restricted",
        excerpt="Restricted excerpt",
        body=[("rich_text", "<p>Restricted</p>")],
        live=False,
    )
    blog_index.add_child(instance=restricted)
    PageViewRestriction.objects.create(
        page=restricted,
        restriction_type=PageViewRestriction.PASSWORD,
        password="test-only",
    )
    publish(restricted)

    assert not EmailOutbox.objects.filter(message_type=EmailOutbox.MessageType.PUBLICATION).exists()


def test_due_scheduled_publication_creates_event(blog_post):
    due = timezone.now() - timedelta(minutes=1)
    blog_post.go_live_at = due
    blog_post.save_revision(approved_go_live_at=due)

    call_command("publish_scheduled_pages", verbosity=0)

    assert publication_event(BlogPostPage.objects.get(pk=blog_post.pk)).audience_cutoff


def test_audience_cutoff_and_unsubscribe_state_are_enforced(blog_post):
    published = publish(blog_post)
    event = publication_event(published)
    before = active_subscriber(
        "before@example.com",
        event.audience_cutoff - timedelta(seconds=1),
    )
    after = active_subscriber(
        "after@example.com",
        event.audience_cutoff + timedelta(seconds=1),
    )
    unsubscribed = active_subscriber(
        "left@example.com",
        event.audience_cutoff - timedelta(seconds=2),
    )
    Subscriber.objects.filter(pk=unsubscribed.pk).update(
        status=Subscriber.Status.UNSUBSCRIBED,
        unsubscribed_at=timezone.now(),
    )
    MemoryEmailProvider.reset()

    assert claim_outbox_batch(limit=10) == [event.pk]
    process_outbox_event(event.pk, provider=MemoryEmailProvider())

    assert EmailDelivery.objects.filter(outbox=event, subscriber=before).get().status == "sent"
    assert (
        EmailDelivery.objects.filter(outbox=event, subscriber=unsubscribed).get().status
        == "skipped"
    )
    assert not EmailDelivery.objects.filter(outbox=event, subscriber=after).exists()
    assert len(MemoryEmailProvider.sent) == 1
    event.refresh_from_db()
    assert event.status == EmailOutbox.Status.DELIVERED


def test_confirmation_is_sent_only_by_worker_with_multipart_body():
    MemoryEmailProvider.reset()
    subscriber = request_subscription("reader@example.com")
    event = subscriber.outbox_events.get()

    assert MemoryEmailProvider.sent == []
    call_command("process_email_outbox", limit=10, verbosity=0)

    assert len(MemoryEmailProvider.sent) == 1
    message, idempotency_key = MemoryEmailProvider.sent[0]
    assert message.to == "reader@example.com"
    assert "Confirm your subscription" in message.subject
    assert "Confirm your subscription" in message.text
    assert "<h1>Confirm your subscription</h1>" in message.html
    assert "#credential=" in message.html
    assert idempotency_key == f"email/{event.deliveries.get().pk}"


def test_publication_template_escapes_values_omits_body_and_has_unsubscribe_headers(
    blog_post,
):
    active_subscriber("reader@example.com", timezone.now() - timedelta(days=1))
    event = publication_event(publish(blog_post))
    MemoryEmailProvider.reset()

    claim_outbox_batch(limit=1)
    process_outbox_event(event.pk, provider=MemoryEmailProvider())

    message, _ = MemoryEmailProvider.sent[0]
    assert "A new &lt;safe&gt; post" in message.html
    assert "&lt;script&gt;" in message.html
    assert "Body that must not enter email" not in message.html
    assert message.headers["List-Unsubscribe"].startswith("<http://localhost:3000/")
    assert message.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "/subscriptions/unsubscribe/" in message.text


class SelectiveProvider(EmailProvider):
    def __init__(self, failures):
        self.failures = failures
        self.calls = []

    def send(self, message, idempotency_key):
        self.calls.append((message.to, idempotency_key))
        if message.to in self.failures:
            raise EmailProviderError("Sanitized provider failure", retryable=True)
        return ProviderSendResult(message_id=f"provider-{len(self.calls)}")


@override_settings(
    EMAIL_OUTBOX_MAX_ATTEMPTS=2,
    EMAIL_OUTBOX_RETRY_BASE_SECONDS=1,
    EMAIL_OUTBOX_RETRY_MAX_SECONDS=2,
)
def test_retry_backoff_terminal_failure_and_one_failure_does_not_block_others(
    blog_post,
):
    base = timezone.now() - timedelta(days=1)
    active_subscriber("ok@example.com", base)
    active_subscriber("fail@example.com", base)
    event = publication_event(publish(blog_post))
    provider = SelectiveProvider({"fail@example.com"})
    first_at = timezone.now()

    claim_outbox_batch(limit=1, at=first_at)
    sent, status = process_outbox_event(event.pk, provider=provider, at=first_at)
    assert sent == 1
    assert status == EmailOutbox.Status.PENDING
    failed_delivery = event.deliveries.get(subscriber__email="fail@example.com")
    assert failed_delivery.status == EmailDelivery.Status.PENDING
    assert failed_delivery.available_at == first_at + timedelta(seconds=1)

    second_at = first_at + timedelta(seconds=2)
    claim_outbox_batch(limit=1, at=second_at)
    sent, status = process_outbox_event(event.pk, provider=provider, at=second_at)
    assert sent == 0
    assert status == EmailOutbox.Status.FAILED
    failed_delivery.refresh_from_db()
    assert failed_delivery.attempt_count == 2
    assert failed_delivery.last_error == "Sanitized provider failure"
    assert event.deliveries.get(subscriber__email="ok@example.com").status == "sent"


def test_claim_reclaims_stale_processing_and_repeat_run_is_safe(blog_post):
    event = publication_event(publish(blog_post))
    old = timezone.now() - timedelta(hours=1)
    EmailOutbox.objects.filter(pk=event.pk).update(
        status=EmailOutbox.Status.PROCESSING,
        processing_at=old,
    )

    claimed = claim_outbox_batch(limit=1)
    assert claimed == [event.pk]
    process_outbox_event(event.pk, provider=MemoryEmailProvider())
    assert claim_outbox_batch(limit=1) == []
    assert event.deliveries.count() == 0


@override_settings(
    EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS=60,
    EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS=10,
)
def test_ambiguous_processing_past_provider_window_fails_without_resend(blog_post):
    subscriber = active_subscriber(
        "reader@example.com",
        timezone.now() - timedelta(days=1),
    )
    event = publication_event(publish(blog_post))
    old = timezone.now() - timedelta(minutes=2)
    EmailOutbox.objects.filter(pk=event.pk).update(
        status=EmailOutbox.Status.PROCESSING,
        processing_at=old,
    )
    delivery = EmailDelivery.objects.create(
        outbox=event,
        subscriber=subscriber,
        status=EmailDelivery.Status.PROCESSING,
        available_at=old,
        processing_at=old,
        attempt_count=1,
    )
    MemoryEmailProvider.reset()

    _, status = process_outbox_event(
        event.pk,
        provider=MemoryEmailProvider(),
    )

    delivery.refresh_from_db()
    assert status == EmailOutbox.Status.FAILED
    assert delivery.status == EmailDelivery.Status.FAILED
    assert "idempotency safety window" in delivery.last_error
    assert MemoryEmailProvider.sent == []


def test_publication_delivery_batch_query_count_is_bounded(blog_post):
    base = timezone.now() - timedelta(days=1)
    Subscriber.objects.bulk_create(
        [
            Subscriber(
                email=f"reader{index}@example.com",
                canonical_email=f"reader{index}@example.com",
                status=Subscriber.Status.ACTIVE,
                confirmed_at=base,
            )
            for index in range(20)
        ]
    )
    event = publication_event(publish(blog_post))
    claim_outbox_batch(limit=1)

    with CaptureQueriesContext(connection) as queries:
        delivery_ids = build_delivery_batch(event.pk, limit=100)

    assert len(delivery_ids) == 20
    assert len(queries) <= 8


class Response:
    status = 200

    def __init__(self, body=b'{"id":"resend-message-id"}'):
        self.body = body

    def read(self):
        return self.body

    def getcode(self):
        return self.status


@override_settings(
    RESEND_API_KEY="test-api-key",
    RESEND_FROM_EMAIL="Posts <posts@example.com>",
)
def test_resend_adapter_sends_exact_api_contract_without_leaking_errors():
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    provider = ResendEmailProvider(opener=opener)
    message = type(
        "Message",
        (),
        {
            "to": "reader@example.com",
            "subject": "Subject",
            "text": "Text",
            "html": "<p>HTML</p>",
            "headers": {"List-Unsubscribe": "<https://example.com>"},
        },
    )()
    result = provider.send(message, "email/immutable-id")

    assert result.message_id == "resend-message-id"
    assert captured["request"].full_url == "https://api.resend.com/emails"
    assert captured["request"].headers["Idempotency-key"] == "email/immutable-id"
    assert captured["request"].headers["Authorization"] == "Bearer test-api-key"
    payload = json.loads(captured["request"].data)
    assert payload["text"] == "Text"
    assert payload["html"] == "<p>HTML</p>"


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (TimeoutError("secret provider body"), True),
        (
            urllib.error.HTTPError(
                "https://api.resend.com/emails",
                422,
                "secret provider body",
                {},
                io.BytesIO(b"secret"),
            ),
            False,
        ),
        (
            urllib.error.HTTPError(
                "https://api.resend.com/emails",
                503,
                "secret provider body",
                {},
                io.BytesIO(b"secret"),
            ),
            True,
        ),
    ],
)
@override_settings(RESEND_API_KEY="test-api-key", RESEND_FROM_EMAIL="posts@example.com")
def test_resend_adapter_classifies_timeout_4xx_and_5xx(error, retryable):
    provider = ResendEmailProvider(opener=lambda request, timeout: (_ for _ in ()).throw(error))
    message = type(
        "Message",
        (),
        {
            "to": "reader@example.com",
            "subject": "Subject",
            "text": "Text",
            "html": "<p>HTML</p>",
            "headers": {},
        },
    )()

    with pytest.raises(EmailProviderError) as captured:
        provider.send(message, "email/immutable-id")

    assert captured.value.retryable is retryable
    assert "secret provider body" not in captured.value.safe_message


def test_management_command_output_contains_no_email_address():
    request_subscription("private-reader@example.com")
    output = io.StringIO()

    call_command("process_email_outbox", stdout=output, verbosity=1)

    assert "private-reader@example.com" not in output.getvalue()
