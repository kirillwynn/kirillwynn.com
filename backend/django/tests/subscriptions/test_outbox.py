import hashlib
import io
import json
import urllib.error
from dataclasses import replace
from datetime import timedelta

import pytest
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import connection, models
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from wagtail.models import Page, PageViewRestriction

from apps.blog.models import BlogPostPage
from apps.subscriptions.message_limits import (
    MAX_EMAIL_SUBJECT_LENGTH,
    MAX_PUBLICATION_EXCERPT_LENGTH,
    MAX_PUBLICATION_TITLE_LENGTH,
    MAX_SNAPSHOT_URL_LENGTH,
)
from apps.subscriptions.messages import message_for_delivery
from apps.subscriptions.models import EmailDelivery, EmailOutbox, Subscriber
from apps.subscriptions.outbox import (
    build_delivery_batch,
    claim_outbox_batch,
    process_outbox_event,
    publication_outbox_snapshot,
)
from apps.subscriptions.providers import configured_email_provider
from apps.subscriptions.providers.base import (
    MAX_PROVIDER_REQUEST_BODY_BYTES,
    EmailProvider,
    EmailProviderError,
    ProviderSendResult,
)
from apps.subscriptions.providers.memory import MemoryEmailProvider
from apps.subscriptions.providers.resend import (
    ResendEmailProvider,
    serialize_resend_request,
)
from apps.subscriptions.services import request_subscription, unsubscribe_with_credential
from apps.subscriptions.tokens import issue_credential

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


def build_pending_publication_delivery(blog_post, *, at=None, provider=None):
    now = at or timezone.now()
    subscriber = active_subscriber(
        f"reader-{blog_post.pk}@example.com",
        now - timedelta(days=1),
    )
    event = publication_event(publish(blog_post))
    if event.available_at > now:
        EmailOutbox.objects.filter(pk=event.pk).update(available_at=now)
        event.available_at = now
    claim_outbox_batch(limit=1, at=now)
    delivery_id = build_delivery_batch(event.pk, limit=1, at=now, provider=provider)[0]
    return subscriber, event, EmailDelivery.objects.get(pk=delivery_id)


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
    prepared_request, idempotency_key = MemoryEmailProvider.sent[0]
    payload = json.loads(prepared_request.body)
    assert payload["to"] == ["reader@example.com"]
    assert "Confirm your subscription" in payload["subject"]
    assert "Confirm your subscription" in payload["text"]
    assert "<h1>Confirm your subscription</h1>" in payload["html"]
    assert "#credential=" in payload["html"]
    assert idempotency_key == f"email/{event.deliveries.get().pk}"


@override_settings(
    EMAIL_PROVIDER_ADAPTER="apps.subscriptions.providers.memory.MemoryEmailProvider",
    EMAIL_FROM_ADDRESS="Memory Sender <memory@example.com>",
    RESEND_API_KEY="",
    RESEND_WEBHOOK_SECRET="",
)
def test_non_resend_production_like_configuration_creates_and_processes_confirmation():
    MemoryEmailProvider.reset()
    subscriber = request_subscription("runtime@example.com")
    event = subscriber.outbox_events.get()

    assert event.snapshot_from_email == "Memory Sender <memory@example.com>"
    assert claim_outbox_batch(limit=1) == [event.pk]
    sent, status = process_outbox_event(event.pk, provider=configured_email_provider())

    delivery = event.deliveries.get()
    assert sent == 1
    assert status == EmailOutbox.Status.DELIVERED
    assert delivery.status == EmailDelivery.Status.SENT
    assert json.loads(MemoryEmailProvider.sent[0][0].body)["from"] == event.snapshot_from_email


@override_settings(EMAIL_FROM_ADDRESS=" \r\n ")
def test_invalid_from_address_fails_before_confirmation_transaction():
    with pytest.raises(ImproperlyConfigured, match="EMAIL_FROM_ADDRESS must be a valid mailbox"):
        request_subscription("runtime@example.com")

    assert Subscriber.objects.count() == 0
    assert EmailOutbox.objects.count() == 0


def test_provider_fingerprint_uses_exact_bytes_selected_by_adapter():
    class CustomBodyProvider(EmailProvider):
        transport_contract_id = "test.custom-body"
        serializer_contract_version = 1

        def __init__(self):
            self.sent_bodies = []

        def serialize_request(self, message):
            return f"custom-body:{message.to}:{message.subject}".encode()

        def send(self, prepared_request, idempotency_key):
            self.sent_bodies.append(prepared_request.body)
            return ProviderSendResult(message_id="custom-body-provider-id")

    subscriber = request_subscription("custom-provider@example.com")
    event = subscriber.outbox_events.get()
    provider = CustomBodyProvider()
    assert claim_outbox_batch(limit=1) == [event.pk]

    sent, status = process_outbox_event(event.pk, provider=provider)

    delivery = event.deliveries.get()
    assert sent == 1
    assert status == EmailOutbox.Status.DELIVERED
    assert delivery.provider_payload_hash == hashlib.sha256(provider.sent_bodies[0]).hexdigest()


class RecordingProvider(EmailProvider):
    transport_contract_id = "test.recording"
    serializer_contract_version = 1

    def __init__(self, *, failures=0):
        self.failures = failures
        self.calls = []
        self.serialize_calls = 0

    def serialize_request(self, message):
        self.serialize_calls += 1
        return super().serialize_request(message)

    def send(self, prepared_request, idempotency_key):
        self.calls.append((prepared_request, idempotency_key))
        if len(self.calls) <= self.failures:
            raise EmailProviderError(
                "Ambiguous provider timeout",
                retryable=True,
                ambiguity_reason=EmailDelivery.AmbiguityReason.TRANSPORT_FAILURE,
            )
        return ProviderSendResult(message_id=f"recording-{len(self.calls)}")


class OtherRecordingProvider(RecordingProvider):
    transport_contract_id = "test.other-recording"


@override_settings(
    EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE="provider-a/production/account-main",
    EMAIL_OUTBOX_RETRY_BASE_SECONDS=1,
    EMAIL_OUTBOX_RETRY_MAX_SECONDS=1,
)
def test_ambiguous_provider_swap_with_identical_bytes_requires_manual_review(blog_post):
    first_at = timezone.now()
    provider_a = RecordingProvider(failures=1)
    _, event, delivery = build_pending_publication_delivery(
        blog_post,
        at=first_at,
        provider=provider_a,
    )
    process_outbox_event(event.pk, provider=provider_a, at=first_at)
    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.PENDING

    retry_at = first_at + timedelta(seconds=2)
    provider_b = OtherRecordingProvider()
    claim_outbox_batch(limit=1, at=retry_at)
    sent, _ = process_outbox_event(event.pk, provider=provider_b, at=retry_at)

    delivery.refresh_from_db()
    assert sent == 0
    assert delivery.status == EmailDelivery.Status.MANUAL_REVIEW
    assert delivery.ambiguity_reason == EmailDelivery.AmbiguityReason.TRANSPORT_IDENTITY_MISMATCH
    assert provider_b.calls == []
    assert provider_a.calls[0][0].body == provider_b.serialize_request(
        message_for_delivery(delivery)
    )


def test_same_adapter_with_different_idempotency_namespace_never_calls_provider(blog_post):
    provider = RecordingProvider()
    with override_settings(EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE="resend/production/account-a"):
        _, event, delivery = build_pending_publication_delivery(
            blog_post,
            provider=provider,
        )

    with override_settings(EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE="resend/production/account-b"):
        sent, _ = process_outbox_event(event.pk, provider=provider)

    delivery.refresh_from_db()
    assert sent == 0
    assert delivery.status == EmailDelivery.Status.MANUAL_REVIEW
    assert delivery.ambiguity_reason == EmailDelivery.AmbiguityReason.IDEMPOTENCY_NAMESPACE_MISMATCH
    assert provider.calls == []


def test_serializer_contract_version_drift_never_calls_provider(blog_post):
    class VersionTwoProvider(RecordingProvider):
        serializer_contract_version = 2

    provider_v1 = RecordingProvider()
    _, event, delivery = build_pending_publication_delivery(
        blog_post,
        provider=provider_v1,
    )
    provider_v2 = VersionTwoProvider()

    sent, _ = process_outbox_event(event.pk, provider=provider_v2)

    delivery.refresh_from_db()
    assert sent == 0
    assert delivery.status == EmailDelivery.Status.MANUAL_REVIEW
    assert delivery.ambiguity_reason == EmailDelivery.AmbiguityReason.SERIALIZER_VERSION_MISMATCH
    assert provider_v2.calls == []


@override_settings(
    EMAIL_OUTBOX_RETRY_BASE_SECONDS=1,
    EMAIL_OUTBOX_RETRY_MAX_SECONDS=1,
)
def test_same_transport_identity_namespace_and_bytes_allows_normal_retry(blog_post):
    first_at = timezone.now()
    provider = RecordingProvider(failures=1)
    _, event, delivery = build_pending_publication_delivery(
        blog_post,
        at=first_at,
        provider=provider,
    )
    process_outbox_event(event.pk, provider=provider, at=first_at)

    retry_at = first_at + timedelta(seconds=2)
    claim_outbox_batch(limit=1, at=retry_at)
    sent, _ = process_outbox_event(event.pk, provider=provider, at=retry_at)

    delivery.refresh_from_db()
    first_request, first_key = provider.calls[0]
    second_request, second_key = provider.calls[1]
    assert sent == 1
    assert delivery.status == EmailDelivery.Status.SENT
    assert first_request.body == second_request.body
    assert first_request.transport == second_request.transport
    assert first_key == second_key == delivery.provider_idempotency_key
    assert provider.serialize_calls == 3


def test_drifting_serializer_cannot_replace_verified_body_inside_send(blog_post):
    class ThirdCallDriftsProvider(RecordingProvider):
        def serialize_request(self, message):
            self.serialize_calls += 1
            body = serialize_resend_request(message)
            return body if self.serialize_calls <= 2 else body + b" "

    provider = ThirdCallDriftsProvider()
    _, event, delivery = build_pending_publication_delivery(
        blog_post,
        provider=provider,
    )

    sent, _ = process_outbox_event(event.pk, provider=provider)

    delivery.refresh_from_db()
    prepared_request, _ = provider.calls[0]
    assert sent == 1
    assert provider.serialize_calls == 2
    assert hashlib.sha256(prepared_request.body).hexdigest() == delivery.provider_payload_hash


def test_prepared_provider_body_is_bounded_before_delivery_creation(blog_post):
    class OversizedProvider(RecordingProvider):
        def serialize_request(self, message):
            return b"x" * (MAX_PROVIDER_REQUEST_BODY_BYTES + 1)

    provider = OversizedProvider()

    with pytest.raises(ValueError, match="bounded non-empty bytes"):
        build_pending_publication_delivery(blog_post, provider=provider)

    assert provider.calls == []
    assert EmailDelivery.objects.count() == 0


def test_different_deliveries_and_targets_keep_independent_transport_keys_and_hashes(
    blog_post,
):
    base = timezone.now() - timedelta(days=1)
    active_subscriber("first-target@example.com", base)
    active_subscriber("second-target@example.com", base)
    event = publication_event(publish(blog_post))
    provider = RecordingProvider()
    claim_outbox_batch(limit=1)

    sent, _ = process_outbox_event(event.pk, provider=provider)

    deliveries = list(event.deliveries.order_by("snapshot_recipient_email"))
    assert sent == 2
    assert len(provider.calls) == 2
    assert len({delivery.provider_payload_hash for delivery in deliveries}) == 2
    assert len({delivery.provider_idempotency_key for delivery in deliveries}) == 2
    assert {delivery.provider_contract_id for delivery in deliveries} == {
        provider.transport_contract_id
    }
    assert {delivery.provider_idempotency_namespace for delivery in deliveries} == {"local/test"}


def test_publication_snapshot_boundaries_cover_maximum_wagtail_inputs(blog_post):
    wagtail_title_length = Page._meta.get_field("title").max_length
    subject_field = EmailOutbox._meta.get_field("snapshot_subject")
    from_field = EmailOutbox._meta.get_field("snapshot_from_email")
    site_url_field = EmailOutbox._meta.get_field("snapshot_site_url")
    post_title_field = EmailOutbox._meta.get_field("snapshot_post_title")
    post_excerpt_field = EmailOutbox._meta.get_field("snapshot_post_excerpt")
    post_url_field = EmailOutbox._meta.get_field("snapshot_post_url")
    recipient_field = EmailDelivery._meta.get_field("snapshot_recipient_email")

    assert wagtail_title_length == MAX_PUBLICATION_TITLE_LENGTH
    assert subject_field.max_length == MAX_EMAIL_SUBJECT_LENGTH
    assert subject_field.max_length >= len("New post: ") + wagtail_title_length
    assert from_field.max_length == 512
    assert site_url_field.max_length == 2_048
    assert post_title_field.max_length == MAX_PUBLICATION_TITLE_LENGTH
    assert isinstance(post_excerpt_field, models.TextField)
    assert isinstance(post_url_field, models.TextField)
    assert recipient_field.max_length == 320

    blog_post.title = "T" * MAX_PUBLICATION_TITLE_LENGTH
    blog_post.excerpt = "E" * MAX_PUBLICATION_EXCERPT_LENGTH
    blog_post.slug = "界" * MAX_PUBLICATION_TITLE_LENGTH
    snapshot = publication_outbox_snapshot(blog_post)

    assert snapshot["snapshot_subject"] == f"New post: {'T' * 255}"
    assert len(snapshot["snapshot_subject"]) == 265
    assert snapshot["snapshot_post_title"] == "T" * MAX_PUBLICATION_TITLE_LENGTH
    assert snapshot["snapshot_post_excerpt"] == "E" * MAX_PUBLICATION_EXCERPT_LENGTH
    assert len(snapshot["snapshot_post_url"]) > 2_048
    assert len(snapshot["snapshot_post_url"]) <= MAX_SNAPSHOT_URL_LENGTH

    canonical_prefix = "https://canonical.example/"
    blog_post.canonical_url = canonical_prefix + ("a" * (2_048 - len(canonical_prefix)))
    assert len(publication_outbox_snapshot(blog_post)["snapshot_post_url"]) == 2_048


def test_maximum_wagtail_title_publishes_without_subject_truncation(blog_post):
    blog_post.title = "T" * MAX_PUBLICATION_TITLE_LENGTH
    published = publish(blog_post)

    event = publication_event(published)
    assert event.snapshot_post_title == blog_post.title
    assert event.snapshot_subject == f"New post: {blog_post.title}"
    assert len(event.snapshot_subject) == 265


def test_publication_template_escapes_values_omits_body_and_has_unsubscribe_headers(
    blog_post,
):
    active_subscriber("reader@example.com", timezone.now() - timedelta(days=1))
    event = publication_event(publish(blog_post))
    MemoryEmailProvider.reset()

    claim_outbox_batch(limit=1)
    process_outbox_event(event.pk, provider=MemoryEmailProvider())

    payload = json.loads(MemoryEmailProvider.sent[0][0].body)
    assert "A new &lt;safe&gt; post" in payload["html"]
    assert "&lt;script&gt;" in payload["html"]
    assert "Body that must not enter email" not in payload["html"]
    assert payload["headers"]["List-Unsubscribe"].startswith("<http://localhost:3000/")
    assert payload["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "/subscriptions/unsubscribe/" in payload["text"]


@override_settings(
    EMAIL_FROM_ADDRESS="Original <posts@example.com>",
    PUBLIC_SITE_URL="https://example.com",
)
def test_delivery_renders_byte_identical_resend_body_after_time_post_and_config_changes(
    blog_post,
    monkeypatch,
):
    _, event, delivery = build_pending_publication_delivery(blog_post)
    original_body = serialize_resend_request(message_for_delivery(delivery))

    BlogPostPage.objects.filter(pk=blog_post.pk).update(
        title="Changed after publication",
        excerpt="Changed excerpt",
        canonical_url="https://elsewhere.example/changed",
    )
    monkeypatch.setattr(
        signing.time,
        "time",
        lambda: (timezone.now() + timedelta(days=30)).timestamp(),
    )
    with override_settings(
        EMAIL_FROM_ADDRESS="Changed <changed@example.com>",
        PUBLIC_SITE_URL="https://changed.example",
    ):
        delivery.refresh_from_db()
        event.refresh_from_db()
        later_body = serialize_resend_request(message_for_delivery(delivery))

    assert later_body == original_body
    assert delivery.provider_payload_hash
    assert b"Changed after publication" not in later_body
    assert b"changed@example.com" not in later_body


def test_payload_fingerprint_mismatch_requires_manual_review_without_provider_call(
    blog_post,
    monkeypatch,
):
    _, event, delivery = build_pending_publication_delivery(blog_post)
    original = message_for_delivery(delivery)
    monkeypatch.setattr(
        "apps.subscriptions.outbox.message_for_delivery",
        lambda current: replace(original, subject="Changed template deployment"),
    )
    provider = SelectiveProvider(set())

    sent, status = process_outbox_event(event.pk, provider=provider)

    delivery.refresh_from_db()
    assert sent == 0
    assert status == EmailOutbox.Status.FAILED
    assert delivery.status == EmailDelivery.Status.MANUAL_REVIEW
    assert delivery.ambiguity_reason == EmailDelivery.AmbiguityReason.PAYLOAD_MISMATCH
    assert provider.calls == []


class SelectiveProvider(EmailProvider):
    transport_contract_id = "memory.email"
    serializer_contract_version = 1

    def __init__(self, failures):
        self.failures = failures
        self.calls = []

    def send(self, prepared_request, idempotency_key):
        recipient = json.loads(prepared_request.body)["to"][0]
        self.calls.append((recipient, idempotency_key))
        if recipient in self.failures:
            raise EmailProviderError("Sanitized provider failure", retryable=True)
        return ProviderSendResult(message_id=f"provider-{len(self.calls)}")


class AlwaysTimeoutProvider(EmailProvider):
    transport_contract_id = "memory.email"
    serializer_contract_version = 1

    def __init__(self):
        self.calls = []

    def send(self, prepared_request, idempotency_key):
        self.calls.append((prepared_request, idempotency_key))
        raise EmailProviderError(
            "Sanitized timeout",
            retryable=True,
            ambiguity_reason=EmailDelivery.AmbiguityReason.TRANSPORT_FAILURE,
        )


@override_settings(
    EMAIL_OUTBOX_RETRY_BASE_SECONDS=1,
    EMAIL_OUTBOX_RETRY_MAX_SECONDS=1,
    EMAIL_OUTBOX_MAX_ATTEMPTS=10,
)
def test_timeout_pending_and_retries_keep_one_absolute_provider_window(blog_post):
    first_at = timezone.now()
    _, event, delivery = build_pending_publication_delivery(blog_post, at=first_at)
    provider = AlwaysTimeoutProvider()

    process_outbox_event(event.pk, provider=provider, at=first_at)
    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.PENDING
    assert delivery.first_provider_attempt_at == first_at

    for retry_at in (first_at + timedelta(hours=1), first_at + timedelta(hours=2)):
        claim_outbox_batch(limit=1, at=retry_at)
        process_outbox_event(event.pk, provider=provider, at=retry_at)
        delivery.refresh_from_db()
        assert delivery.first_provider_attempt_at == first_at
        assert delivery.last_provider_attempt_at == retry_at
        assert delivery.processing_at is None

    assert len(provider.calls) == 3
    assert len({request.body for request, _ in provider.calls}) == 1
    assert len({request.transport for request, _ in provider.calls}) == 1
    assert {key for _, key in provider.calls} == {delivery.provider_idempotency_key}
    assert provider.calls[0][0].transport.contract_id == delivery.provider_contract_id
    assert (
        provider.calls[0][0].transport.idempotency_namespace
        == delivery.provider_idempotency_namespace
    )


@override_settings(
    EMAIL_OUTBOX_RETRY_BASE_SECONDS=1,
    EMAIL_OUTBOX_RETRY_MAX_SECONDS=1,
    EMAIL_OUTBOX_MAX_ATTEMPTS=10,
)
def test_retry_at_hour_22_is_allowed_but_worker_after_deadline_never_calls_provider(
    blog_post,
):
    first_at = timezone.now()
    _, event, delivery = build_pending_publication_delivery(blog_post, at=first_at)
    provider = AlwaysTimeoutProvider()
    process_outbox_event(event.pk, provider=provider, at=first_at)

    hour_22 = first_at + timedelta(hours=22)
    claim_outbox_batch(limit=1, at=hour_22)
    process_outbox_event(event.pk, provider=provider, at=hour_22)
    assert len(provider.calls) == 2

    after_deadline = first_at + timedelta(hours=24)
    claim_outbox_batch(limit=1, at=after_deadline)
    sent, status = process_outbox_event(event.pk, provider=provider, at=after_deadline)

    delivery.refresh_from_db()
    assert sent == 0
    assert status == EmailOutbox.Status.FAILED
    assert delivery.status == EmailDelivery.Status.MANUAL_REVIEW
    assert delivery.ambiguity_reason == EmailDelivery.AmbiguityReason.WINDOW_EXPIRED
    assert len(provider.calls) == 2


@override_settings(
    EMAIL_PROVIDER_IDEMPOTENCY_WINDOW_SECONDS=60,
    EMAIL_OUTBOX_PROCESSING_TIMEOUT_SECONDS=10,
)
def test_crashed_processing_attempt_uses_first_provider_attempt_not_reclaim_lease(
    blog_post,
):
    first_at = timezone.now()
    _, event, delivery = build_pending_publication_delivery(blog_post, at=first_at)
    EmailDelivery.objects.filter(pk=delivery.pk).update(
        status=EmailDelivery.Status.PROCESSING,
        processing_at=first_at,
        attempt_count=1,
        first_provider_attempt_at=first_at,
        last_provider_attempt_at=first_at,
        ambiguity_reason=EmailDelivery.AmbiguityReason.TRANSPORT_FAILURE,
    )
    EmailOutbox.objects.filter(pk=event.pk).update(
        status=EmailOutbox.Status.PROCESSING,
        processing_at=first_at,
    )
    provider = SelectiveProvider(set())
    after_deadline = first_at + timedelta(seconds=61)

    sent, status = process_outbox_event(event.pk, provider=provider, at=after_deadline)

    delivery.refresh_from_db()
    assert sent == 0
    assert status == EmailOutbox.Status.FAILED
    assert delivery.status == EmailDelivery.Status.MANUAL_REVIEW
    assert delivery.first_provider_attempt_at == first_at
    assert provider.calls == []


def test_provider_acceptance_wins_in_flight_unsubscribe_but_subscriber_stays_unsubscribed(
    blog_post,
):
    subscriber, event, delivery = build_pending_publication_delivery(blog_post)
    credential = issue_credential(
        subscriber=subscriber,
        purpose="unsubscribe",
        token_version=subscriber.unsubscribe_token_version,
        issued_at=delivery.credential_issued_at,
    )

    class UnsubscribingProvider(EmailProvider):
        transport_contract_id = "memory.email"
        serializer_contract_version = 1
        calls = 0

        def send(self, prepared_request, idempotency_key):
            self.calls += 1
            unsubscribe_with_credential(credential)
            delivery.refresh_from_db()
            assert delivery.status == EmailDelivery.Status.PROCESSING
            return ProviderSendResult(message_id="accepted-during-unsubscribe")

    provider = UnsubscribingProvider()
    sent, _ = process_outbox_event(event.pk, provider=provider)

    subscriber.refresh_from_db()
    delivery.refresh_from_db()
    assert sent == 1
    assert provider.calls == 1
    assert subscriber.status == Subscriber.Status.UNSUBSCRIBED
    assert delivery.status == EmailDelivery.Status.SENT
    assert delivery.provider_message_id == "accepted-during-unsubscribe"


def test_unsubscribe_never_marks_ambiguous_pending_attempt_as_cancelled(blog_post):
    subscriber, event, delivery = build_pending_publication_delivery(blog_post)
    provider = AlwaysTimeoutProvider()
    process_outbox_event(event.pk, provider=provider)
    delivery.refresh_from_db()
    credential = issue_credential(
        subscriber=subscriber,
        purpose="unsubscribe",
        token_version=subscriber.unsubscribe_token_version,
        issued_at=delivery.credential_issued_at,
    )

    unsubscribe_with_credential(credential)

    subscriber.refresh_from_db()
    delivery.refresh_from_db()
    assert subscriber.status == Subscriber.Status.UNSUBSCRIBED
    assert delivery.status == EmailDelivery.Status.MANUAL_REVIEW
    assert delivery.ambiguity_reason == EmailDelivery.AmbiguityReason.IN_FLIGHT_CANCELLED


@pytest.mark.parametrize("change", ["unpublish", "expire", "restrict"])
def test_publication_revalidated_before_first_provider_call(blog_post, change):
    _, event, delivery = build_pending_publication_delivery(blog_post)
    post = BlogPostPage.objects.get(pk=blog_post.pk)
    if change == "unpublish":
        post.unpublish()
    elif change == "expire":
        BlogPostPage.objects.filter(pk=post.pk).update(
            expire_at=timezone.now() - timedelta(seconds=1)
        )
    else:
        PageViewRestriction.objects.create(
            page=post,
            restriction_type=PageViewRestriction.PASSWORD,
            password="test-only",
        )
    provider = SelectiveProvider(set())

    sent, status = process_outbox_event(event.pk, provider=provider)

    delivery.refresh_from_db()
    assert sent == 0
    assert status == EmailOutbox.Status.DELIVERED
    assert delivery.status == EmailDelivery.Status.SKIPPED
    assert provider.calls == []


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
        snapshot_recipient_email=subscriber.email,
        snapshot_credential_version=subscriber.unsubscribe_token_version,
        credential_issued_at=old,
        provider_contract_id="memory.email",
        provider_serializer_version=1,
        provider_idempotency_namespace="local/test",
        provider_payload_hash="0" * 64,
        first_provider_attempt_at=old,
        last_provider_attempt_at=old,
        ambiguity_reason=EmailDelivery.AmbiguityReason.TRANSPORT_FAILURE,
    )
    MemoryEmailProvider.reset()

    _, status = process_outbox_event(
        event.pk,
        provider=MemoryEmailProvider(),
    )

    delivery.refresh_from_db()
    assert status == EmailOutbox.Status.FAILED
    assert delivery.status == EmailDelivery.Status.MANUAL_REVIEW
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

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]

    def getcode(self):
        return self.status


@override_settings(
    RESEND_API_KEY="test-api-key",
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
            "from_email": "Posts <posts@example.com>",
            "to": "reader@example.com",
            "subject": "Subject",
            "text": "Text",
            "html": "<p>HTML</p>",
            "headers": {"List-Unsubscribe": "<https://example.com>"},
        },
    )()
    prepared_request = provider.prepare_request(message)
    result = provider.send(prepared_request, "email/immutable-id")

    assert result.message_id == "resend-message-id"
    assert captured["request"].full_url == "https://api.resend.com/emails"
    assert captured["request"].headers["Idempotency-key"] == "email/immutable-id"
    assert captured["request"].headers["Authorization"] == "Bearer test-api-key"
    assert captured["request"].data is prepared_request.body
    payload = json.loads(captured["request"].data)
    assert payload["text"] == "Text"
    assert payload["html"] == "<p>HTML</p>"


@override_settings(
    RESEND_API_KEY="super-secret-api-key",
    EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE=" Resend/Staging/Account-Test ",
)
def test_worker_sends_the_exact_verified_resend_body_once_per_attempt(blog_post):
    captured = {}

    class CountingResendProvider(ResendEmailProvider):
        def __init__(self):
            super().__init__(opener=self.capture)
            self.serialize_calls = 0

        def serialize_request(self, message):
            self.serialize_calls += 1
            return super().serialize_request(message)

        def capture(self, request, timeout):
            captured["body"] = request.data
            captured["key"] = request.headers["Idempotency-key"]
            captured["timeout"] = timeout
            return Response()

    provider = CountingResendProvider()
    _, event, delivery = build_pending_publication_delivery(
        blog_post,
        provider=provider,
    )

    sent, _ = process_outbox_event(event.pk, provider=provider)

    delivery.refresh_from_db()
    assert sent == 1
    assert provider.serialize_calls == 2
    assert hashlib.sha256(captured["body"]).hexdigest() == delivery.provider_payload_hash
    assert captured["key"] == delivery.provider_idempotency_key
    assert delivery.provider_contract_id == "resend.emails"
    assert delivery.provider_serializer_version == 1
    assert delivery.provider_idempotency_namespace == "resend/staging/account-test"
    assert "super-secret-api-key" not in (
        delivery.provider_contract_id + delivery.provider_idempotency_namespace
    )


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
@override_settings(RESEND_API_KEY="test-api-key")
def test_resend_adapter_classifies_timeout_4xx_and_5xx(error, retryable):
    provider = ResendEmailProvider(opener=lambda request, timeout: (_ for _ in ()).throw(error))
    message = type(
        "Message",
        (),
        {
            "from_email": "posts@example.com",
            "to": "reader@example.com",
            "subject": "Subject",
            "text": "Text",
            "html": "<p>HTML</p>",
            "headers": {},
        },
    )()

    with pytest.raises(EmailProviderError) as captured:
        provider.send(provider.prepare_request(message), "email/immutable-id")

    assert captured.value.retryable is retryable
    assert "secret provider body" not in captured.value.safe_message


@pytest.mark.parametrize(
    ("error_type", "retryable", "ambiguity_reason"),
    [
        (
            "invalid_idempotent_request",
            False,
            EmailDelivery.AmbiguityReason.PAYLOAD_MISMATCH,
        ),
        (
            "concurrent_idempotent_requests",
            True,
            EmailDelivery.AmbiguityReason.CONCURRENT_REQUEST,
        ),
        ("future_unknown_conflict", False, "provider_failure"),
    ],
)
@override_settings(RESEND_API_KEY="test-api-key")
def test_resend_adapter_classifies_official_and_unknown_409_variants(
    error_type,
    retryable,
    ambiguity_reason,
):
    body = json.dumps(
        {
            "name": error_type,
            "message": "secret provider response must not persist",
        }
    ).encode()
    error = urllib.error.HTTPError(
        "https://api.resend.com/emails",
        409,
        "secret provider response must not persist",
        {},
        io.BytesIO(body),
    )
    provider = ResendEmailProvider(opener=lambda request, timeout: (_ for _ in ()).throw(error))
    message = type(
        "Message",
        (),
        {
            "from_email": "posts@example.com",
            "to": "reader@example.com",
            "subject": "Subject",
            "text": "Text",
            "html": "<p>HTML</p>",
            "headers": {},
        },
    )()

    with pytest.raises(EmailProviderError) as captured:
        provider.send(provider.prepare_request(message), "email/immutable-id")

    assert captured.value.retryable is retryable
    assert captured.value.ambiguity_reason == ambiguity_reason
    assert "secret provider response" not in captured.value.safe_message


@override_settings(
    RESEND_API_KEY="test-api-key",
    RESEND_SUCCESS_RESPONSE_MAX_BODY_BYTES=16,
    RESEND_ERROR_RESPONSE_MAX_BODY_BYTES=16,
)
def test_resend_adapter_bounds_success_and_error_response_bodies():
    message = type(
        "Message",
        (),
        {
            "from_email": "posts@example.com",
            "to": "reader@example.com",
            "subject": "Subject",
            "text": "Text",
            "html": "<p>HTML</p>",
            "headers": {},
        },
    )()
    success_provider = ResendEmailProvider(opener=lambda request, timeout: Response(b"x" * 17))
    oversized_error = urllib.error.HTTPError(
        "https://api.resend.com/emails",
        503,
        "secret",
        {},
        io.BytesIO(b"x" * 17),
    )
    error_provider = ResendEmailProvider(
        opener=lambda request, timeout: (_ for _ in ()).throw(oversized_error)
    )

    with pytest.raises(EmailProviderError) as success:
        success_provider.send(success_provider.prepare_request(message), "email/success")
    with pytest.raises(EmailProviderError) as failure:
        error_provider.send(error_provider.prepare_request(message), "email/error")

    assert success.value.safe_message == "Resend returned an oversized response"
    assert failure.value.safe_message == "Resend HTTP 503 (oversized error response)"


def test_management_command_output_contains_no_email_address():
    request_subscription("private-reader@example.com")
    output = io.StringIO()

    call_command("process_email_outbox", stdout=output, verbosity=1)

    assert "private-reader@example.com" not in output.getvalue()
