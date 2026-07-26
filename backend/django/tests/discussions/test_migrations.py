import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


def test_discussions_migration_reverses_and_applies_from_zero():
    executor = MigrationExecutor(connection)
    leaf = executor.loader.graph.leaf_nodes("discussions")

    executor.migrate([("discussions", None)])
    assert "discussions_comment" not in connection.introspection.table_names()
    assert "discussions_commentratelimitbucket" not in connection.introspection.table_names()
    assert "discussions_postreaction" not in connection.introspection.table_names()
    assert "discussions_commentreaction" not in connection.introspection.table_names()

    executor = MigrationExecutor(connection)
    executor.migrate(leaf)
    tables = connection.introspection.table_names()
    assert "discussions_comment" in tables
    assert "discussions_commentratelimitbucket" in tables
    assert "discussions_postreaction" in tables
    assert "discussions_commentreaction" in tables
    assert "discussions_reactionsettings" in tables
    assert "discussions_reactionratelimitbucket" in tables
