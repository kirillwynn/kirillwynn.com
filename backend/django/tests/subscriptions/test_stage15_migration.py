from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from wagtail.models import Locale, Page

from apps.blog.models import BlogIndexPage, BlogPostPage
from apps.subscriptions.models import EmailDelivery, EmailOutbox, Subscriber
from apps.subscriptions.outbox import publication_outbox_snapshot

pytestmark = pytest.mark.django_db(transaction=True)

PREVIOUS_MIGRATION = ("subscriptions", "0003_bind_delivery_transport_identity")
STAGE15_MIGRATION = ("subscriptions", "0004_post_publication_email_decision")


def add_post(blog_index, slug):
    post = BlogPostPage(
        title=slug.replace("-", " ").title(),
        slug=slug,
        excerpt=f"Excerpt for {slug}.",
        body=[("rich_text", f"<p>Body for {slug}.</p>")],
        live=False,
    )
    blog_index.add_child(instance=post)
    return post


def test_stage15_backfill_round_trip_preserves_email_history_and_never_creates_email():
    executor = MigrationExecutor(connection)
    executor.migrate([PREVIOUS_MIGRATION])

    locale, _ = Locale.objects.get_or_create(language_code="en")
    root = Page.get_first_root_node()
    if root is None:
        root = Page.add_root(
            instance=Page(
                title="Root",
                slug="root",
                locale=locale,
            )
        )
    blog_index = BlogIndexPage(title="Blog", slug="blog", live=False)
    root.add_child(instance=blog_index)

    now = timezone.now()
    queued_post = add_post(blog_index, "queued-before-migration")
    suppressed_post = add_post(blog_index, "published-without-event")
    draft_post = add_post(blog_index, "never-published-draft")
    scheduled_post = add_post(blog_index, "future-scheduled-draft")
    scheduled_post.go_live_at = now + timedelta(days=1)
    scheduled_post.save()
    Page.objects.filter(pk__in=(queued_post.pk, suppressed_post.pk)).update(
        first_published_at=now - timedelta(days=1),
        last_published_at=now,
    )
    queued_post.refresh_from_db()

    cutoff = now - timedelta(hours=12)
    event = EmailOutbox.objects.create(
        post=queued_post,
        message_type=EmailOutbox.MessageType.PUBLICATION,
        audience_cutoff=cutoff,
        available_at=cutoff,
        idempotency_key=f"publication/{queued_post.pk}",
        **publication_outbox_snapshot(queued_post),
    )
    subscriber = Subscriber.objects.create(
        email="historical-reader@example.com",
        status=Subscriber.Status.ACTIVE,
        confirmed_at=cutoff - timedelta(days=1),
    )
    delivery = EmailDelivery.objects.create(
        outbox=event,
        subscriber=subscriber,
        status=EmailDelivery.Status.SENT,
        available_at=cutoff,
        snapshot_recipient_email=subscriber.email,
        snapshot_credential_version=1,
        credential_issued_at=cutoff,
        provider_contract_id="resend.emails",
        provider_serializer_version=1,
        provider_idempotency_namespace="resend/staging/account",
        provider_payload_hash="a" * 64,
        first_provider_attempt_at=cutoff,
        last_provider_attempt_at=cutoff,
        provider_message_id="historical-stage15-message-id",
        provider_created_at=cutoff,
        sent_at=cutoff,
    )
    event_snapshot = {
        "id": event.pk,
        "audience_cutoff": event.audience_cutoff,
        "subject": event.snapshot_subject,
        "url": event.snapshot_post_url,
    }
    delivery_snapshot = {
        "id": delivery.pk,
        "provider_message_id": delivery.provider_message_id,
        "provider_contract_id": delivery.provider_contract_id,
        "provider_payload_hash": delivery.provider_payload_hash,
    }
    outbox_count = EmailOutbox.objects.count()
    delivery_count = EmailDelivery.objects.count()

    executor = MigrationExecutor(connection)
    executor.migrate([STAGE15_MIGRATION])
    migrated_apps = executor.loader.project_state([STAGE15_MIGRATION]).apps
    Decision = migrated_apps.get_model(
        "subscriptions",
        "PostPublicationEmailDecision",
    )

    queued = Decision.objects.get(post_id=queued_post.pk)
    suppressed = Decision.objects.get(post_id=suppressed_post.pk)
    draft = Decision.objects.get(post_id=draft_post.pk)
    scheduled = Decision.objects.get(post_id=scheduled_post.pk)
    assert (queued.state, queued.decided_at, queued.outbox_id) == (
        "queued",
        cutoff,
        event.pk,
    )
    assert suppressed.state == "suppressed"
    assert suppressed.decided_at == now - timedelta(days=1)
    assert suppressed.outbox_id is None
    assert (draft.state, draft.decided_at, draft.outbox_id) == (
        "pending",
        None,
        None,
    )
    assert (scheduled.state, scheduled.decided_at, scheduled.outbox_id) == (
        "pending",
        None,
        None,
    )
    assert EmailOutbox.objects.count() == outbox_count
    assert EmailDelivery.objects.count() == delivery_count

    executor = MigrationExecutor(connection)
    executor.migrate([PREVIOUS_MIGRATION])
    assert (
        "subscriptions_postpublicationemaildecision" not in connection.introspection.table_names()
    )
    event.refresh_from_db()
    delivery.refresh_from_db()
    assert {
        "id": event.pk,
        "audience_cutoff": event.audience_cutoff,
        "subject": event.snapshot_subject,
        "url": event.snapshot_post_url,
    } == event_snapshot
    assert {
        "id": delivery.pk,
        "provider_message_id": delivery.provider_message_id,
        "provider_contract_id": delivery.provider_contract_id,
        "provider_payload_hash": delivery.provider_payload_hash,
    } == delivery_snapshot
    assert EmailOutbox.objects.count() == outbox_count
    assert EmailDelivery.objects.count() == delivery_count

    executor = MigrationExecutor(connection)
    executor.migrate([STAGE15_MIGRATION])
    reapplied_apps = executor.loader.project_state([STAGE15_MIGRATION]).apps
    ReappliedDecision = reapplied_apps.get_model(
        "subscriptions",
        "PostPublicationEmailDecision",
    )
    assert ReappliedDecision.objects.get(post_id=queued_post.pk).state == "queued"
    assert ReappliedDecision.objects.get(post_id=suppressed_post.pk).state == "suppressed"
    assert ReappliedDecision.objects.get(post_id=draft_post.pk).state == "pending"
    assert ReappliedDecision.objects.get(post_id=scheduled_post.pk).state == "pending"
    assert EmailOutbox.objects.count() == outbox_count
    assert EmailDelivery.objects.count() == delivery_count
