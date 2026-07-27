import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

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
