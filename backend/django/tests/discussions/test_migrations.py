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
    PostReaction.objects.bulk_create([PostReaction(post=public_post, user=user, emoji="🔥")])
    CommentReaction.objects.bulk_create([CommentReaction(comment=comment, user=user, emoji="👩‍💻")])
    post_reaction = PostReaction.objects.get(post=public_post, user=user)
    comment_reaction = CommentReaction.objects.get(comment=comment, user=user)
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


def test_catalog_identity_activation_constraint_reverses_with_populated_rows(
    public_post,
    user,
    reaction_catalog_items,
):
    first_item, second_item, _ = reaction_catalog_items
    comment = create_top_level_comment(post=public_post, author=user, body="Mixed")
    PostReaction.objects.bulk_create([PostReaction(post=public_post, user=user, emoji="🔥")])
    CommentReaction.objects.bulk_create([CommentReaction(comment=comment, user=user, emoji="👩‍💻")])
    custom_post = PostReaction.objects.create(
        post=public_post,
        user=user,
        catalog_item=first_item,
    )
    second_custom_post = PostReaction.objects.create(
        post=public_post,
        user=user,
        catalog_item=second_item,
    )
    custom_comment = CommentReaction.objects.create(
        comment=comment,
        user=user,
        catalog_item=first_item,
    )
    second_custom_comment = CommentReaction.objects.create(
        comment=comment,
        user=user,
        catalog_item=second_item,
    )
    expansion = ("discussions", "0003_reaction_catalog_expansion")
    activation = ("discussions", "0004_activate_catalog_reaction_identity")

    executor = MigrationExecutor(connection)
    leaf = executor.loader.graph.leaf_nodes("discussions")
    try:
        executor.migrate([expansion])
        expanded_apps = executor.loader.project_state([expansion]).apps
        ExpandedPostReaction = expanded_apps.get_model(
            "discussions",
            "PostReaction",
        )
        assert ExpandedPostReaction.objects.get(pk=custom_post.pk).emoji == ""

        executor = MigrationExecutor(connection)
        executor.migrate([activation])
        activated_apps = executor.loader.project_state([activation]).apps
        ActivatedPostReaction = activated_apps.get_model(
            "discussions",
            "PostReaction",
        )
        ActivatedCommentReaction = activated_apps.get_model(
            "discussions",
            "CommentReaction",
        )
        assert (
            ActivatedPostReaction.objects.filter(
                post_id=public_post.pk,
                user_id=user.pk,
            ).count()
            == 3
        )
        assert (
            ActivatedCommentReaction.objects.filter(
                comment_id=comment.pk,
                user_id=user.pk,
            ).count()
            == 3
        )
        assert ActivatedPostReaction.objects.get(pk=custom_post.pk).catalog_item_id
        assert ActivatedPostReaction.objects.get(pk=second_custom_post.pk).catalog_item_id
        assert ActivatedCommentReaction.objects.get(pk=custom_comment.pk).catalog_item_id
        assert ActivatedCommentReaction.objects.get(pk=second_custom_comment.pk).catalog_item_id

        executor = MigrationExecutor(connection)
        executor.migrate([expansion])
        reversed_apps = executor.loader.project_state([expansion]).apps
        ReversedPostReaction = reversed_apps.get_model(
            "discussions",
            "PostReaction",
        )
        ReversedCommentReaction = reversed_apps.get_model(
            "discussions",
            "CommentReaction",
        )
        reversed_posts = ReversedPostReaction.objects.filter(
            post_id=public_post.pk,
            user_id=user.pk,
        )
        reversed_comments = ReversedCommentReaction.objects.filter(
            comment_id=comment.pk,
            user_id=user.pk,
        )
        assert reversed_posts.count() == reversed_comments.count() == 3
        assert list(reversed_posts.values_list("emoji", flat=True)).count("") == 2
        assert list(reversed_comments.values_list("emoji", flat=True)).count("") == 2
        assert set(reversed_posts.values_list("catalog_item_id", flat=True)) == {
            None,
            first_item.catalog_id,
            second_item.catalog_id,
        }
        assert set(reversed_comments.values_list("catalog_item_id", flat=True)) == {
            None,
            first_item.catalog_id,
            second_item.catalog_id,
        }

        executor = MigrationExecutor(connection)
        executor.migrate([activation])
        reapplied_apps = executor.loader.project_state([activation]).apps
        assert (
            reapplied_apps.get_model("discussions", "PostReaction")
            .objects.filter(post_id=public_post.pk, user_id=user.pk)
            .count()
            == 3
        )
        assert (
            reapplied_apps.get_model("discussions", "CommentReaction")
            .objects.filter(comment_id=comment.pk, user_id=user.pk)
            .count()
            == 3
        )
    finally:
        MigrationExecutor(connection).migrate(leaf)
