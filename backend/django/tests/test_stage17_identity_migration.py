from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.utils import timezone
from wagtail.models import Locale, Page

from apps.blog.models import BlogIndexPage, BlogPostPage
from apps.discussions.models import Comment

pytestmark = pytest.mark.django_db(transaction=True)

EXPANSION = ("users", "0002_stage17_identity_expansion")
BACKFILL = ("users", "0003_stage17_identity_backfill")


def _public_post(owner=None):
    locale, _ = Locale.objects.get_or_create(language_code="en")
    root = Page.get_first_root_node()
    if root is None:
        root = Page.add_root(instance=Page(title="Root", slug="root", locale=locale))
    index = BlogIndexPage(title="Identity migration", slug="identity-migration", live=True)
    root.add_child(instance=index)
    post = BlogPostPage(
        title="Identity migration post",
        slug="identity-migration-post",
        excerpt="Migration fixture.",
        body=[("rich_text", "<p>Fixture.</p>")],
        live=True,
        owner=owner,
    )
    index.add_child(instance=post)
    Page.objects.filter(pk=post.pk).update(
        live=True,
        first_published_at=timezone.now() - timedelta(days=1),
        last_published_at=timezone.now(),
    )
    post.refresh_from_db()
    return post


def test_stage17_populated_forward_reverse_forward_preserves_identity_and_content():
    User = get_user_model()
    owner = User.objects.create_user(
        username="owner-internal",
        email="Owner@Example.com",
        password="owner-passphrase",
        first_name="Kirill",
        last_name="Wynn",
        is_staff=True,
        is_superuser=True,
    )
    commenter = User.objects.create_user(
        username="reader-one",
        email="reader@example.com",
        password="reader-passphrase",
        first_name="Åke",
    )
    incomplete = User.objects.create_user(
        username="reader-two",
        email="READER@example.com",
        password="second-passphrase",
        first_name="A\u030ake",
    )
    social_only = User.objects.create_user(
        username="github-social-123",
        email="social@example.com",
        first_name="\u674e \u96f7",
    )
    social_only.set_unusable_password()
    social_only.is_active = False
    social_only.is_banned = True
    social_only.save(update_fields=("password", "is_active", "is_banned"))

    EmailAddress.objects.create(
        user=owner,
        email=owner.email,
        primary=True,
        verified=True,
    )
    EmailAddress.objects.create(
        user=commenter,
        email=commenter.email,
        primary=True,
        verified=True,
    )
    EmailAddress.objects.create(
        user=incomplete,
        email=incomplete.email,
        primary=True,
        verified=False,
    )
    SocialAccount.objects.create(user=social_only, provider="github", uid="migration-social")
    post = _public_post()
    comment = Comment.objects.create(post=post, author=commenter, body="Existing public content")
    session = Session.objects.create(
        session_key="stage17migrationpreservedsession",
        session_data="preserved-session-payload",
        expire_date=timezone.now() + timedelta(days=1),
    )
    password_snapshots = {
        user.pk: user.password for user in (owner, commenter, incomplete, social_only)
    }
    user_ids = {owner.pk, commenter.pk, incomplete.pk, social_only.pk}

    MigrationExecutor(connection).migrate([EXPANSION])

    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        executor = MigrationExecutor(connection)
        executor.migrate([BACKFILL])
    migrated_apps = executor.loader.project_state([BACKFILL]).apps
    MigratedUser = migrated_apps.get_model("users", "User")
    History = migrated_apps.get_model("users", "NicknameHistory")
    migrated_owner = MigratedUser.objects.get(pk=owner.pk)
    migrated_commenter = MigratedUser.objects.get(pk=commenter.pk)
    migrated_incomplete = MigratedUser.objects.get(pk=incomplete.pk)
    migrated_social = MigratedUser.objects.get(pk=social_only.pk)

    assert migrated_owner.nickname == "Kirill Wynn"
    assert migrated_owner.nickname_confirmed is True
    assert migrated_owner.email_normalized == "owner@example.com"
    assert migrated_commenter.nickname == "Åke"
    assert migrated_commenter.nickname_confirmed is True
    assert migrated_incomplete.nickname.startswith("Åke-")
    assert migrated_incomplete.nickname_confirmed is False
    assert migrated_incomplete.email_normalized is None
    assert migrated_social.nickname == "\u674e \u96f7"
    assert migrated_social.nickname_confirmed is False
    assert migrated_social.is_active is False
    assert migrated_social.is_banned is True
    assert History.objects.count() == len(user_ids)
    assert len(set(History.objects.values_list("nickname_normalized", flat=True))) == len(user_ids)

    Page.objects.get(pk=post.pk).refresh_from_db()
    assert Page.objects.get(pk=post.pk).owner_id == owner.pk
    assert Comment.objects.get(pk=comment.pk).author_id == commenter.pk
    assert SocialAccount.objects.get(uid="migration-social").user_id == social_only.pk
    assert Session.objects.get(pk=session.pk).session_data == "preserved-session-payload"
    assert set(MigratedUser.objects.values_list("pk", flat=True)) >= user_ids
    assert {
        user.pk: user.password for user in MigratedUser.objects.filter(pk__in=user_ids)
    } == password_snapshots
    assert EmailAddress.objects.get(user_id=owner.pk).verified is True
    assert EmailAddress.objects.get(user_id=incomplete.pk).verified is False

    first_mapping = list(
        MigratedUser.objects.filter(pk__in=user_ids)
        .order_by("pk")
        .values_list(
            "pk",
            "email_normalized",
            "nickname",
            "nickname_normalized",
            "nickname_confirmed",
        )
    )
    MigrationExecutor(connection).migrate([EXPANSION])
    expanded_apps = MigrationExecutor(connection).loader.project_state([EXPANSION]).apps
    ExpandedUser = expanded_apps.get_model("users", "User")
    assert not expanded_apps.get_model("users", "NicknameHistory").objects.exists()
    assert not ExpandedUser.objects.filter(pk__in=user_ids, nickname__isnull=False).exists()

    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        executor = MigrationExecutor(connection)
        executor.migrate([BACKFILL])
    reapplied_apps = executor.loader.project_state([BACKFILL]).apps
    assert (
        list(
            reapplied_apps.get_model("users", "User")
            .objects.filter(pk__in=user_ids)
            .order_by("pk")
            .values_list(
                "pk",
                "email_normalized",
                "nickname",
                "nickname_normalized",
                "nickname_confirmed",
            )
        )
        == first_mapping
    )
    assert Page.objects.get(pk=post.pk).owner_id == owner.pk
    assert Comment.objects.get(pk=comment.pk).author_id == commenter.pk
    assert SocialAccount.objects.get(uid="migration-social").user_id == social_only.pk
    assert Session.objects.get(pk=session.pk).session_data == "preserved-session-payload"
