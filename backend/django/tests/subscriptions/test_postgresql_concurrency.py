from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from apps.subscriptions.models import EmailOutbox, Subscriber
from apps.subscriptions.outbox import claim_outbox_batch
from apps.subscriptions.rate_limits import consume_rate_limit

pytestmark = [
    pytest.mark.django_db(transaction=True),
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
