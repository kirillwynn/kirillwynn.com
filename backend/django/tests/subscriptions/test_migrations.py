import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

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
