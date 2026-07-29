import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from apps.discussions.models import CommentReaction, PostReaction
from apps.discussions.services import create_top_level_comment

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
    assert "discussions_reactioncatalogitem" in tables


def test_reaction_catalog_expansion_preserves_populated_unicode_rows_forward_and_reverse(
    public_post,
    user,
):
    comment = create_top_level_comment(post=public_post, author=user, body="Legacy")
    post_reaction = PostReaction.objects.create(post=public_post, user=user, emoji="🔥")
    comment_reaction = CommentReaction.objects.create(
        comment=comment,
        user=user,
        emoji="👩‍💻",
    )
    expansion = ("discussions", "0003_reaction_catalog_expansion")
    legacy = ("discussions", "0002_reactionratelimitbucket_reactionsettings_and_more")

    executor = MigrationExecutor(connection)
    leaf = executor.loader.graph.leaf_nodes("discussions")
    try:
        executor.migrate([legacy])
        legacy_apps = executor.loader.project_state([legacy]).apps
        LegacyPostReaction = legacy_apps.get_model("discussions", "PostReaction")
        LegacyCommentReaction = legacy_apps.get_model("discussions", "CommentReaction")
        assert LegacyPostReaction.objects.get(pk=post_reaction.pk).emoji == "🔥"
        assert LegacyCommentReaction.objects.get(pk=comment_reaction.pk).emoji == "👩‍💻"

        executor = MigrationExecutor(connection)
        executor.migrate([expansion])
        expanded_apps = executor.loader.project_state([expansion]).apps
        ExpandedPostReaction = expanded_apps.get_model("discussions", "PostReaction")
        ExpandedCommentReaction = expanded_apps.get_model("discussions", "CommentReaction")
        expanded_post = ExpandedPostReaction.objects.get(pk=post_reaction.pk)
        expanded_comment = ExpandedCommentReaction.objects.get(pk=comment_reaction.pk)
        assert (expanded_post.emoji, expanded_post.catalog_item_id) == ("🔥", None)
        assert (expanded_comment.emoji, expanded_comment.catalog_item_id) == ("👩‍💻", None)

        executor = MigrationExecutor(connection)
        executor.migrate([legacy])
        reversed_apps = executor.loader.project_state([legacy]).apps
        assert (
            reversed_apps.get_model("discussions", "PostReaction")
            .objects.get(pk=post_reaction.pk)
            .emoji
            == "🔥"
        )
        assert (
            reversed_apps.get_model("discussions", "CommentReaction")
            .objects.get(pk=comment_reaction.pk)
            .emoji
            == "👩‍💻"
        )
    finally:
        MigrationExecutor(connection).migrate(leaf)
