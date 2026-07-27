from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from wagtail.models import Locale, Page

from apps.blog.models import BlogIndexPage, BlogPostPage

pytestmark = pytest.mark.django_db(transaction=True)


def test_subscriptions_migration_reverses_and_reapplies():
    executor = MigrationExecutor(connection)
    leaf = executor.loader.graph.leaf_nodes("subscriptions")

    executor.migrate([("subscriptions", None)])
    tables = connection.introspection.table_names()
    assert "subscriptions_subscriber" not in tables
    assert "subscriptions_emailoutbox" not in tables
    assert "subscriptions_emaildelivery" not in tables
    assert "subscriptions_emailwebhookevent" not in tables

    executor = MigrationExecutor(connection)
    executor.migrate(leaf)
    tables = connection.introspection.table_names()
    assert "subscriptions_subscriber" in tables
    assert "subscriptions_emailoutbox" in tables
    assert "subscriptions_emaildelivery" in tables
    assert "subscriptions_emailwebhookevent" in tables
    assert "subscriptions_subscriptionratelimitbucket" in tables


def test_subscriptions_0002_reverses_and_reapplies_without_drift():
    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0001_initial")])
    columns = {
        column.name
        for column in connection.introspection.get_table_description(
            connection.cursor(),
            "subscriptions_emaildelivery",
        )
    }
    assert "first_provider_attempt_at" not in columns

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0002_harden_email_delivery")])
    columns = {
        column.name
        for column in connection.introspection.get_table_description(
            connection.cursor(),
            "subscriptions_emaildelivery",
        )
    }
    assert "first_provider_attempt_at" in columns
    assert "provider_payload_hash" in columns

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0001_initial")])
    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0002_harden_email_delivery")])


def test_subscriptions_0003_reverses_and_reapplies_without_drift():
    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0002_harden_email_delivery")])
    columns = {
        column.name
        for column in connection.introspection.get_table_description(
            connection.cursor(),
            "subscriptions_emaildelivery",
        )
    }
    assert "provider_contract_id" not in columns

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0003_bind_delivery_transport_identity")])
    columns = {
        column.name
        for column in connection.introspection.get_table_description(
            connection.cursor(),
            "subscriptions_emaildelivery",
        )
    }
    assert {
        "provider_contract_id",
        "provider_serializer_version",
        "provider_idempotency_namespace",
    } <= columns

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0002_harden_email_delivery")])
    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0003_bind_delivery_transport_identity")])


def test_subscriptions_0003_populated_round_trip_quarantines_retryable_and_keeps_history():
    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0002_harden_email_delivery")])
    old_apps = executor.loader.project_state([("subscriptions", "0002_harden_email_delivery")]).apps
    Subscriber = old_apps.get_model("subscriptions", "Subscriber")
    EmailOutbox = old_apps.get_model("subscriptions", "EmailOutbox")
    EmailDelivery = old_apps.get_model("subscriptions", "EmailDelivery")
    now = timezone.now()
    delivery_ids = {}
    for index, status in enumerate(("pending", "processing", "sent")):
        subscriber = Subscriber.objects.create(
            email=f"transport-migration-{index}@example.com",
            canonical_email=f"transport-migration-{index}@example.com",
        )
        outbox = EmailOutbox.objects.create(
            message_type="confirmation",
            subscriber=subscriber,
            credential_version=1,
            available_at=now,
            idempotency_key=f"migration/transport/{index}",
            message_schema_version=1,
            snapshot_from_email="Posts <posts@example.com>",
            snapshot_site_url="https://example.com",
            snapshot_subject="Confirm",
        )
        values = {
            "outbox": outbox,
            "subscriber": subscriber,
            "status": status,
            "available_at": now,
            "snapshot_recipient_email": subscriber.email,
            "snapshot_credential_version": 1,
            "credential_issued_at": now,
            "provider_payload_hash": "0" * 64,
        }
        if status == "processing":
            values["processing_at"] = now
        if status == "sent":
            values.update(
                {
                    "provider_message_id": "historical-message",
                    "provider_created_at": now,
                    "sent_at": now,
                    "first_provider_attempt_at": now,
                    "last_provider_attempt_at": now,
                }
            )
        delivery_ids[status] = EmailDelivery.objects.create(**values).pk

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0003_bind_delivery_transport_identity")])
    new_apps = executor.loader.project_state(
        [("subscriptions", "0003_bind_delivery_transport_identity")]
    ).apps
    MigratedDelivery = new_apps.get_model("subscriptions", "EmailDelivery")
    pending = MigratedDelivery.objects.get(pk=delivery_ids["pending"])
    processing = MigratedDelivery.objects.get(pk=delivery_ids["processing"])
    historical = MigratedDelivery.objects.get(pk=delivery_ids["sent"])

    for delivery in (pending, processing):
        assert delivery.status == "manual_review"
        assert delivery.processing_at is None
        assert delivery.ambiguity_reason == "legacy_transport_identity"
        assert delivery.provider_contract_id == "legacy.unknown"
        assert delivery.provider_idempotency_namespace == "legacy.unknown"
    assert historical.status == "sent"
    assert historical.provider_message_id == "historical-message"
    assert historical.provider_contract_id == "legacy.unknown"
    assert historical.provider_idempotency_namespace == "legacy.unknown"

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0002_harden_email_delivery")])
    reversed_apps = executor.loader.project_state(
        [("subscriptions", "0002_harden_email_delivery")]
    ).apps
    ReversedDelivery = reversed_apps.get_model("subscriptions", "EmailDelivery")
    pending = ReversedDelivery.objects.get(pk=delivery_ids["pending"])
    processing = ReversedDelivery.objects.get(pk=delivery_ids["processing"])
    historical = ReversedDelivery.objects.get(pk=delivery_ids["sent"])

    for delivery in (pending, processing):
        assert delivery.status == "manual_review"
        assert delivery.processing_at is None
        assert delivery.ambiguity_reason == "payload_mismatch"
        assert "transport identity was removed" in delivery.last_error.lower()
        assert len(delivery.last_error) <= 500
    assert historical.status == "sent"
    assert historical.provider_message_id == "historical-message"
    assert historical.provider_created_at == now
    assert historical.sent_at == now
    assert historical.first_provider_attempt_at == now
    assert historical.last_provider_attempt_at == now

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0003_bind_delivery_transport_identity")])
    reapplied_apps = executor.loader.project_state(
        [("subscriptions", "0003_bind_delivery_transport_identity")]
    ).apps
    ReappliedDelivery = reapplied_apps.get_model("subscriptions", "EmailDelivery")
    for status in ("pending", "processing"):
        delivery = ReappliedDelivery.objects.get(pk=delivery_ids[status])
        assert delivery.status == "manual_review"
        assert delivery.ambiguity_reason == "payload_mismatch"
        assert delivery.provider_contract_id == "legacy.unknown"
        assert delivery.provider_idempotency_namespace == "legacy.unknown"
    historical = ReappliedDelivery.objects.get(pk=delivery_ids["sent"])
    assert historical.status == "sent"
    assert historical.provider_message_id == "historical-message"
    assert historical.provider_created_at == now
    assert historical.sent_at == now
    assert historical.first_provider_attempt_at == now
    assert historical.last_provider_attempt_at == now


def test_subscriptions_0003_reverse_normalizes_new_reasons_and_known_pending_identity():
    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0003_bind_delivery_transport_identity")])
    latest_apps = executor.loader.project_state(
        [("subscriptions", "0003_bind_delivery_transport_identity")]
    ).apps
    Subscriber = latest_apps.get_model("subscriptions", "Subscriber")
    EmailOutbox = latest_apps.get_model("subscriptions", "EmailOutbox")
    EmailDelivery = latest_apps.get_model("subscriptions", "EmailDelivery")
    now = timezone.now()
    delivery_ids = {}
    new_reasons = (
        "transport_identity_mismatch",
        "serializer_version_mismatch",
        "idempotency_namespace_mismatch",
        "legacy_transport_identity",
    )
    for index, reason in enumerate(new_reasons):
        subscriber = Subscriber.objects.create(
            email=f"reverse-reason-{index}@example.com",
            canonical_email=f"reverse-reason-{index}@example.com",
        )
        outbox = EmailOutbox.objects.create(
            message_type="confirmation",
            subscriber=subscriber,
            credential_version=1,
            available_at=now,
            idempotency_key=f"migration/reverse-reason/{index}",
            message_schema_version=1,
            snapshot_from_email="Posts <posts@example.com>",
            snapshot_site_url="https://example.com",
            snapshot_subject="Confirm",
        )
        delivery_ids[reason] = EmailDelivery.objects.create(
            outbox=outbox,
            subscriber=subscriber,
            status="manual_review",
            available_at=now,
            snapshot_recipient_email=subscriber.email,
            snapshot_credential_version=1,
            credential_issued_at=now,
            provider_payload_hash="0" * 64,
            provider_contract_id="resend.emails",
            provider_serializer_version=1,
            provider_idempotency_namespace="resend/test",
            ambiguity_reason=reason,
            last_error=f"Latest reason: {reason}",
        ).pk

    pending_subscriber = Subscriber.objects.create(
        email="known-pending@example.com",
        canonical_email="known-pending@example.com",
    )
    pending_outbox = EmailOutbox.objects.create(
        message_type="confirmation",
        subscriber=pending_subscriber,
        credential_version=1,
        available_at=now,
        idempotency_key="migration/known-pending",
        message_schema_version=1,
        snapshot_from_email="Posts <posts@example.com>",
        snapshot_site_url="https://example.com",
        snapshot_subject="Confirm",
    )
    pending_id = EmailDelivery.objects.create(
        outbox=pending_outbox,
        subscriber=pending_subscriber,
        status="pending",
        available_at=now,
        snapshot_recipient_email=pending_subscriber.email,
        snapshot_credential_version=1,
        credential_issued_at=now,
        provider_payload_hash="0" * 64,
        provider_contract_id="resend.emails",
        provider_serializer_version=1,
        provider_idempotency_namespace="resend/test",
    ).pk

    reverse_data = import_module(
        "apps.subscriptions.migrations.0003_bind_delivery_transport_identity"
    ).prepare_deliveries_for_0002
    reverse_data(latest_apps, None)
    first_reverse_state = list(
        EmailDelivery.objects.filter(pk__in=(*delivery_ids.values(), pending_id))
        .order_by("pk")
        .values_list(
            "pk",
            "status",
            "processing_at",
            "ambiguity_reason",
            "last_error",
        )
    )
    reverse_data(latest_apps, None)
    assert (
        list(
            EmailDelivery.objects.filter(pk__in=(*delivery_ids.values(), pending_id))
            .order_by("pk")
            .values_list(
                "pk",
                "status",
                "processing_at",
                "ambiguity_reason",
                "last_error",
            )
        )
        == first_reverse_state
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0002_harden_email_delivery")])
    reversed_apps = executor.loader.project_state(
        [("subscriptions", "0002_harden_email_delivery")]
    ).apps
    ReversedDelivery = reversed_apps.get_model("subscriptions", "EmailDelivery")

    for delivery_id in delivery_ids.values():
        delivery = ReversedDelivery.objects.get(pk=delivery_id)
        assert delivery.status == "manual_review"
        assert delivery.ambiguity_reason == "payload_mismatch"
        assert "during downgrade" in delivery.last_error
        assert len(delivery.last_error) <= 500
    pending = ReversedDelivery.objects.get(pk=pending_id)
    assert pending.status == "manual_review"
    assert pending.processing_at is None
    assert pending.ambiguity_reason == "payload_mismatch"
    assert "transport identity was removed" in pending.last_error.lower()
    assert len(pending.last_error) <= 500


def test_subscriptions_0002_safely_backfills_existing_ambiguous_and_webhook_rows():
    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0001_initial")])
    old_apps = executor.loader.project_state([("subscriptions", "0001_initial")]).apps
    Subscriber = old_apps.get_model("subscriptions", "Subscriber")
    EmailOutbox = old_apps.get_model("subscriptions", "EmailOutbox")
    EmailDelivery = old_apps.get_model("subscriptions", "EmailDelivery")
    EmailWebhookEvent = old_apps.get_model("subscriptions", "EmailWebhookEvent")
    now = timezone.now()
    subscriber = Subscriber.objects.create(
        email="migration@example.com",
        canonical_email="migration@example.com",
    )
    outbox = EmailOutbox.objects.create(
        message_type="confirmation",
        subscriber=subscriber,
        credential_version=1,
        status="processing",
        available_at=now,
        processing_at=now,
        idempotency_key="migration/confirmation",
    )
    delivery = EmailDelivery.objects.create(
        outbox=outbox,
        subscriber=subscriber,
        status="processing",
        available_at=now,
        processing_at=now,
        provider_message_id="migration-provider-message",
    )
    EmailWebhookEvent.objects.create(
        event_id="migration-webhook",
        event_type="email.delivered",
        delivery=delivery,
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0002_harden_email_delivery")])
    new_apps = executor.loader.project_state([("subscriptions", "0002_harden_email_delivery")]).apps
    migrated_delivery = new_apps.get_model("subscriptions", "EmailDelivery").objects.get(
        pk=delivery.pk
    )
    migrated_webhook = new_apps.get_model("subscriptions", "EmailWebhookEvent").objects.get(
        event_id="migration-webhook"
    )

    assert migrated_delivery.status == "manual_review"
    assert migrated_delivery.ambiguity_reason == "payload_mismatch"
    assert migrated_delivery.snapshot_recipient_email == "migration@example.com"
    assert migrated_webhook.processing_state == "applied"
    assert migrated_webhook.provider_message_id == "migration-provider-message"
    assert migrated_webhook.delivery_id == delivery.pk


def test_subscriptions_0002_backfills_maximum_publication_title_without_truncation():
    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0001_initial")])
    Locale.objects.get_or_create(language_code="en")
    root = Page.get_first_root_node()
    if root is None:
        root = Page.add_root(instance=Page(title="Root", slug="root"))
    blog_index = BlogIndexPage(title="Migration blog", slug="migration-blog", live=False)
    root.add_child(instance=blog_index)
    blog_post = BlogPostPage(
        title="T" * 255,
        slug="界" * 255,
        excerpt="Migration excerpt",
        body=[],
        live=False,
    )
    blog_index.add_child(instance=blog_post)
    old_apps = executor.loader.project_state([("subscriptions", "0001_initial")]).apps
    EmailOutbox = old_apps.get_model("subscriptions", "EmailOutbox")
    HistoricalBlogPost = old_apps.get_model("blog", "BlogPostPage")
    historical_post = HistoricalBlogPost.objects.get(pk=blog_post.pk)
    now = timezone.now()
    old_event = EmailOutbox.objects.create(
        message_type="publication",
        post_id=historical_post.pk,
        audience_cutoff=now,
        available_at=now,
        idempotency_key="migration/publication/max-title",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("subscriptions", "0002_harden_email_delivery")])
    new_apps = executor.loader.project_state([("subscriptions", "0002_harden_email_delivery")]).apps
    MigratedOutbox = new_apps.get_model("subscriptions", "EmailOutbox")
    migrated = MigratedOutbox.objects.get(pk=old_event.pk)

    assert migrated.snapshot_post_title == "T" * 255
    assert migrated.snapshot_subject == f"New post: {'T' * 255}"
    assert len(migrated.snapshot_subject) == 265
    assert len(migrated.snapshot_post_url) > 2_048
    assert MigratedOutbox._meta.get_field("snapshot_subject").max_length == 512
    assert MigratedOutbox._meta.get_field("snapshot_post_url").get_internal_type() == "TextField"
