from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone
from wagtail.models import Locale, Page

from apps.blog.models import BlogIndexPage, BlogPostPage
from apps.subscriptions.models import (
    EmailOutbox,
    PostPublicationEmailDecision,
    Subscriber,
)
from apps.subscriptions.outbox import (
    claim_outbox_batch,
    confirmation_outbox_snapshot,
    decide_publication_email,
)
from apps.subscriptions.rate_limits import consume_rate_limit

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.postgresql,
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="Outbox skip-locked and bucket races require PostgreSQL.",
    ),
]


def _run_concurrently(functions):
    barrier = Barrier(len(functions))

    def run(function):
        close_old_connections()
        barrier.wait()
        try:
            return function()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        return [future.result() for future in [executor.submit(run, fn) for fn in functions]]


def test_parallel_claimers_claim_event_once():
    subscriber = Subscriber.objects.create(email="reader@example.com")
    event = EmailOutbox.objects.create(
        message_type=EmailOutbox.MessageType.CONFIRMATION,
        subscriber=subscriber,
        credential_version=1,
        available_at=timezone.now(),
        idempotency_key=f"confirmation/{subscriber.pk}/1",
        **confirmation_outbox_snapshot(),
    )

    results = _run_concurrently(
        [
            lambda: claim_outbox_batch(limit=1),
            lambda: claim_outbox_batch(limit=1),
        ]
    )

    assert sum(event.pk in result for result in results) == 1


def test_parallel_rate_limit_creation_keeps_one_hashed_bucket():
    scope = "subscribe_ip"
    _run_concurrently(
        [
            lambda: consume_rate_limit(scope=scope, value="192.0.2.1"),
            lambda: consume_rate_limit(scope=scope, value="192.0.2.1"),
        ]
    )

    from apps.subscriptions.models import SubscriptionRateLimitBucket

    bucket = SubscriptionRateLimitBucket.objects.get(scope=scope)
    assert bucket.request_count == 2


def test_parallel_first_publication_decision_creates_one_event():
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
    post = BlogPostPage(
        title="Concurrent publication",
        slug="concurrent-publication",
        excerpt="Concurrent publication excerpt.",
        body=[("rich_text", "<p>Concurrent publication.</p>")],
        live=False,
    )
    blog_index.add_child(instance=post)
    now = timezone.now()
    BlogPostPage.objects.filter(pk=post.pk).update(
        live=True,
        first_published_at=now,
        last_published_at=now,
    )
    PostPublicationEmailDecision.objects.create(post_id=post.pk)

    states = _run_concurrently(
        [
            lambda: decide_publication_email(
                BlogPostPage.objects.get(pk=post.pk),
            ).state,
            lambda: decide_publication_email(
                BlogPostPage.objects.get(pk=post.pk),
            ).state,
        ]
    )

    decision = PostPublicationEmailDecision.objects.get(post_id=post.pk)
    assert states == [
        PostPublicationEmailDecision.State.QUEUED,
        PostPublicationEmailDecision.State.QUEUED,
    ]
    assert decision.state == PostPublicationEmailDecision.State.QUEUED
    assert (
        EmailOutbox.objects.filter(
            post_id=post.pk,
            message_type=EmailOutbox.MessageType.PUBLICATION,
        ).count()
        == 1
    )
