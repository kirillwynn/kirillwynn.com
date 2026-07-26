from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.discussions.models import Comment
from apps.discussions.services import (
    create_reply,
    create_top_level_comment,
    edit_comment,
    set_comment_hidden,
    soft_delete_comment,
)

pytestmark = pytest.mark.django_db


def test_root_and_reply_keep_one_depth_and_derive_mention(public_post, user, other_user):
    root = create_top_level_comment(post=public_post, author=user, body=" Root\r\nbody ")
    first_reply = create_reply(target_id=root.pk, author=other_user, body="First")
    reply_to_reply = create_reply(target_id=first_reply.pk, author=user, body="Second")

    assert root.thread_root_id is None
    assert root.body == "Root\nbody"
    assert first_reply.thread_root_id == root.pk
    assert first_reply.reply_to_user_id == user.pk
    assert reply_to_reply.thread_root_id == root.pk
    assert reply_to_reply.reply_to_user_id == other_user.pk


def test_cross_post_recursive_and_self_roots_are_rejected(
    public_post, blog_index, user, other_user
):
    second_post = type(public_post)(
        title="Second",
        slug="second",
        excerpt="Second.",
        body=[("rich_text", "<p>Second.</p>")],
        live=False,
    )
    blog_index.add_child(instance=second_post)
    second_post.save_revision().publish()
    root = create_top_level_comment(post=public_post, author=user, body="Root")
    other_root = create_top_level_comment(post=second_post, author=user, body="Other")
    reply = create_reply(target_id=root.pk, author=other_user, body="Reply")

    cross_post = Comment(
        post=second_post,
        author=other_user,
        thread_root=root,
        reply_to_user=user,
        body="Invalid",
    )
    recursive = Comment(
        post=public_post,
        author=other_user,
        thread_root=reply,
        reply_to_user=user,
        body="Invalid",
    )
    self_root = Comment(
        id=99_999,
        post=public_post,
        author=user,
        thread_root_id=99_999,
        reply_to_user=user,
        body="Invalid",
    )

    with pytest.raises(ValidationError):
        cross_post.full_clean()
    with pytest.raises(ValidationError):
        recursive.full_clean()
    with pytest.raises(ValidationError):
        self_root.full_clean()
    assert other_root.thread_root_id is None


def test_database_constraints_protect_reply_and_moderation_shapes(public_post, user):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Comment.objects.create(
                post=public_post,
                author=user,
                reply_to_user=user,
                body="Top level mention is invalid.",
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Comment.objects.create(
                post=public_post,
                author=user,
                body="Invalid hidden shape.",
                moderation_state=Comment.ModerationState.HIDDEN,
            )


def test_edit_noop_delete_and_moderation_timestamps(public_post, user, admin_user, monkeypatch):
    created = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: created)
    comment = create_top_level_comment(post=public_post, author=user, body="Original")
    initial_updated = comment.updated_at

    noop = edit_comment(comment_id=comment.pk, actor=user, body=" Original ")
    assert noop.edited_at is None
    assert noop.updated_at == initial_updated

    edited_at = created + timedelta(minutes=1)
    monkeypatch.setattr(timezone, "now", lambda: edited_at)
    edited = edit_comment(comment_id=comment.pk, actor=user, body="Changed")
    assert edited.edited_at == edited_at

    hidden = set_comment_hidden(comment_id=comment.pk, moderator=admin_user, hidden=True)
    assert hidden.public_status == "hidden"
    assert hidden.moderated_by_id == admin_user.pk
    visible = set_comment_hidden(comment_id=comment.pk, moderator=admin_user, hidden=False)
    assert visible.public_status == "visible"
    assert visible.moderated_by_id is None

    deleted = soft_delete_comment(comment_id=comment.pk, actor=user)
    deleted_again = soft_delete_comment(comment_id=comment.pk, actor=user)
    assert deleted.public_status == "deleted"
    assert deleted_again.deleted_at == deleted.deleted_at


def test_root_replies_survive_soft_delete_and_hard_delete_is_protected(
    public_post, user, other_user
):
    root = create_top_level_comment(post=public_post, author=user, body="Root")
    reply = create_reply(target_id=root.pk, author=other_user, body="Reply")

    soft_delete_comment(comment_id=root.pk, actor=user)

    assert Comment.objects.filter(pk=reply.pk, thread_root=root).exists()
    with pytest.raises(ProtectedError):
        root.delete()
    with pytest.raises(ProtectedError):
        user.delete()
