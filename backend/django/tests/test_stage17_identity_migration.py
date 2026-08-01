from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.utils import timezone
from wagtail.models import Locale, Page

from apps.blog.models import BlogIndexPage, BlogPostPage
from apps.discussions.models import Comment
from apps.users.models import NicknameHistory
from tests.identity import create_identity_user

pytestmark = pytest.mark.django_db(transaction=True)

EXPANSION = ("users", "0002_stage17_identity_expansion")
BACKFILL = ("users", "0003_stage17_identity_backfill")
ACTIVATION = ("users", "0005_stage17_activation_catchup")


@pytest.fixture(autouse=True)
def restore_current_migration_graph():
    yield
    executor = MigrationExecutor(connection)
    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        executor.migrate(executor.loader.graph.leaf_nodes())


def _public_post(owner=None, *, owner_id=None, slug="identity-migration-post"):
    locale, _ = Locale.objects.get_or_create(language_code="en")
    root = Page.get_first_root_node()
    if root is None:
        root = Page.add_root(instance=Page(title="Root", slug="root", locale=locale))
    index = BlogIndexPage(
        title="Identity migration",
        slug=f"identity-migration-{slug}",
        live=True,
    )
    root.add_child(instance=index)
    post = BlogPostPage(
        title="Identity migration post",
        slug=slug,
        excerpt="Migration fixture.",
        body=[("rich_text", "<p>Fixture.</p>")],
        live=True,
        owner_id=owner_id if owner_id is not None else getattr(owner, "pk", None),
    )
    index.add_child(instance=post)
    Page.objects.filter(pk=post.pk).update(
        live=True,
        first_published_at=timezone.now() - timedelta(days=1),
        last_published_at=timezone.now(),
    )
    post.refresh_from_db()
    return post


def _draft_post(owner=None, *, owner_id=None, slug="identity-migration-draft"):
    post = _public_post(owner=owner, owner_id=owner_id, slug=slug)
    Page.objects.filter(pk=post.pk).update(live=False, first_published_at=None)
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

    # The expansion migration intentionally quarantines the second member of a
    # case-insensitive legacy email collision. Activation must fail closed on
    # such rows; give this disposable fixture a unique address only so the
    # teardown can restore the current migration graph for subsequent tests.
    reapplied_apps.get_model("users", "User").objects.filter(pk=incomplete.pk).update(
        email="reader-two@example.com",
        email_normalized="reader-two@example.com",
    )
    EmailAddress.objects.filter(user_id=incomplete.pk).update(
        email="reader-two@example.com",
    )


def test_stage17_activation_catches_expansion_window_users_and_repairs_only_proven_owner():
    current_owner = get_user_model().objects.create_superuser(
        username="owner-internal",
        email="owner@example.com",
        email_normalized="owner@example.com",
        nickname="Site Owner",
        nickname_normalized="site owner",
        nickname_confirmed=True,
        is_site_author=True,
        password="owner-passphrase",
    )
    NicknameHistory.objects.create(
        user=current_owner,
        nickname="Site Owner",
        nickname_normalized="site owner",
        change_kind="backfill",
        reason="Existing expansion backfill",
    )
    owned = _public_post(owner=current_owner, slug="owned-before-activation")
    ownerless = _public_post(slug="ownerless-before-activation")
    ownerless_draft = _draft_post(slug="ownerless-draft-before-activation")

    MigrationExecutor(connection).migrate([BACKFILL])
    executor = MigrationExecutor(connection)
    historical_apps = executor.loader.project_state([BACKFILL]).apps
    HistoricalUser = historical_apps.get_model("users", "User")
    catchup = HistoricalUser.objects.create(
        username="expansion-window-reader",
        email="Window@Example.com",
        first_name="Window",
        last_name="Reader",
    )
    EmailAddress.objects.create(
        user_id=catchup.pk,
        email="Window@Example.com",
        primary=True,
        verified=False,
    )
    SocialAccount.objects.create(
        user_id=catchup.pk,
        provider="github",
        uid="expansion-window-social",
    )
    comment = Comment.objects.create(
        post_id=owned.pk,
        author_id=catchup.pk,
        body="Expansion-window public content",
    )
    session = Session.objects.create(
        session_key="stage17activationpreservedsession",
        session_data="activation-session-payload",
        expire_date=timezone.now() + timedelta(days=1),
    )

    with override_settings(SITE_OWNER_EMAIL=""):
        executor = MigrationExecutor(connection)
        executor.migrate([ACTIVATION])
    activated_apps = executor.loader.project_state([ACTIVATION]).apps
    ActivatedUser = activated_apps.get_model("users", "User")
    ActivatedHistory = activated_apps.get_model("users", "NicknameHistory")
    activated_owner = ActivatedUser.objects.get(pk=current_owner.pk)
    activated_catchup = ActivatedUser.objects.get(pk=catchup.pk)
    staff_history = ActivatedHistory.objects.create(
        user_id=current_owner.pk,
        nickname="Reviewed Override",
        nickname_normalized="reviewed override",
        change_kind="staff_override",
        actor_id=current_owner.pk,
        reason="Stage 17 activation catch-up",
    )
    first_mapping = (
        activated_catchup.email,
        activated_catchup.email_normalized,
        activated_catchup.nickname,
        activated_catchup.nickname_normalized,
        activated_catchup.nickname_confirmed,
    )

    assert activated_owner.is_site_author is True
    assert first_mapping == (
        "window@example.com",
        "window@example.com",
        "Window Reader",
        "window reader",
        True,
    )
    assert (
        ActivatedHistory.objects.filter(
            user_id=catchup.pk,
            reason="Stage 17 activation catch-up",
        ).count()
        == 1
    )
    assert Page.objects.get(pk=ownerless.pk).owner_id == current_owner.pk
    assert Page.objects.get(pk=ownerless_draft.pk).owner_id == current_owner.pk
    assert Comment.objects.get(pk=comment.pk).author_id == catchup.pk
    assert SocialAccount.objects.get(uid="expansion-window-social").user_id == catchup.pk
    assert Session.objects.get(pk=session.pk).session_data == "activation-session-payload"

    MigrationExecutor(connection).migrate([BACKFILL])
    reversed_apps = MigrationExecutor(connection).loader.project_state([BACKFILL]).apps
    reversed_catchup = reversed_apps.get_model("users", "User").objects.get(pk=catchup.pk)
    assert reversed_catchup.nickname is None
    assert reversed_catchup.email_normalized is None
    assert (
        not reversed_apps.get_model("users", "NicknameHistory")
        .objects.filter(
            user_id=catchup.pk,
            reason="Stage 17 activation catch-up",
        )
        .exists()
    )
    assert (
        reversed_apps.get_model("users", "NicknameHistory")
        .objects.filter(
            pk=staff_history.pk,
            change_kind="staff_override",
        )
        .exists()
    )
    # Proven page-owner repair is additive and deliberately survives rollback.
    assert Page.objects.get(pk=ownerless.pk).owner_id == current_owner.pk
    assert Page.objects.get(pk=ownerless_draft.pk).owner_id == current_owner.pk

    with override_settings(SITE_OWNER_EMAIL=""):
        executor = MigrationExecutor(connection)
        executor.migrate([ACTIVATION])
    reapplied_apps = executor.loader.project_state([ACTIVATION]).apps
    reapplied = reapplied_apps.get_model("users", "User").objects.get(pk=catchup.pk)
    assert (
        reapplied.email,
        reapplied.email_normalized,
        reapplied.nickname,
        reapplied.nickname_normalized,
        reapplied.nickname_confirmed,
    ) == first_mapping
    assert (
        reapplied_apps.get_model("users", "NicknameHistory")
        .objects.filter(
            user_id=catchup.pk,
            reason="Stage 17 activation catch-up",
        )
        .count()
        == 1
    )


def test_stage17_activation_reverse_preserves_a_post_activation_rename_and_claims():
    current_owner = create_identity_user(
        username="rollback-owner",
        email="owner@example.com",
        nickname="Rollback Owner",
        password="owner-passphrase",
        superuser=True,
        site_author=True,
    )
    _public_post(owner=current_owner, slug="rollback-rename-owner-proof")
    MigrationExecutor(connection).migrate([BACKFILL])
    historical_apps = MigrationExecutor(connection).loader.project_state([BACKFILL]).apps
    catchup = historical_apps.get_model("users", "User").objects.create(
        username="rollback-window-reader",
        email="rollback-reader@example.com",
        first_name="Rollback",
        last_name="Reader",
    )

    with override_settings(SITE_OWNER_EMAIL=""):
        executor = MigrationExecutor(connection)
        executor.migrate([ACTIVATION])
    activated_apps = executor.loader.project_state([ACTIVATION]).apps
    ActivatedUser = activated_apps.get_model("users", "User")
    ActivatedHistory = activated_apps.get_model("users", "NicknameHistory")
    activated = ActivatedUser.objects.get(pk=catchup.pk)
    catchup_key = activated.nickname_normalized
    renamed_display = "Renamed After Activation"
    renamed_key = "renamed after activation"
    ActivatedHistory.objects.create(
        user_id=catchup.pk,
        nickname=renamed_display,
        nickname_normalized=renamed_key,
        change_kind="change",
        reason="Post-activation rename fixture",
    )
    ActivatedUser.objects.filter(pk=catchup.pk).update(
        nickname=renamed_display,
        nickname_normalized=renamed_key,
        nickname_confirmed=True,
        nickname_changed_at=timezone.now(),
    )

    MigrationExecutor(connection).migrate([BACKFILL])
    reversed_apps = MigrationExecutor(connection).loader.project_state([BACKFILL]).apps
    reversed_user = reversed_apps.get_model("users", "User").objects.get(pk=catchup.pk)
    reversed_claims = set(
        reversed_apps.get_model("users", "NicknameHistory")
        .objects.filter(user_id=catchup.pk)
        .values_list("nickname_normalized", flat=True)
    )
    assert reversed_user.nickname == renamed_display
    assert reversed_user.nickname_normalized == renamed_key
    assert reversed_user.email_normalized == "rollback-reader@example.com"
    assert reversed_claims == {catchup_key, renamed_key}

    with override_settings(SITE_OWNER_EMAIL=""):
        executor = MigrationExecutor(connection)
        executor.migrate([ACTIVATION])
    reapplied_apps = executor.loader.project_state([ACTIVATION]).apps
    reapplied_user = reapplied_apps.get_model("users", "User").objects.get(pk=catchup.pk)
    reapplied_claims = set(
        reapplied_apps.get_model("users", "NicknameHistory")
        .objects.filter(user_id=catchup.pk)
        .values_list("nickname_normalized", flat=True)
    )
    assert reapplied_user.nickname == renamed_display
    assert reapplied_user.nickname_normalized == renamed_key
    assert reapplied_claims == {catchup_key, renamed_key}


def test_stage17_activation_allocates_a_catchup_site_author_before_colliding_users():
    MigrationExecutor(connection).migrate([BACKFILL])
    historical_apps = MigrationExecutor(connection).loader.project_state([BACKFILL]).apps
    HistoricalUser = historical_apps.get_model("users", "User")
    competitor = HistoricalUser.objects.create(
        username="catchup-competitor",
        email="competitor@example.com",
        first_name="Kirill",
        last_name="Wynn",
    )
    owner = HistoricalUser.objects.create(
        username="catchup-owner",
        email="owner@example.com",
        first_name="Kirill",
        last_name="Wynn",
    )

    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        executor = MigrationExecutor(connection)
        executor.migrate([ACTIVATION])
    ActivatedUser = executor.loader.project_state([ACTIVATION]).apps.get_model("users", "User")
    activated_owner = ActivatedUser.objects.get(pk=owner.pk)
    activated_competitor = ActivatedUser.objects.get(pk=competitor.pk)

    assert activated_owner.nickname == "Kirill Wynn"
    assert activated_owner.nickname_confirmed is True
    assert activated_owner.is_site_author is True
    assert activated_competitor.nickname == f"Kirill Wynn-{competitor.pk}"
    assert activated_competitor.nickname_confirmed is False


def test_stage17_activation_fails_closed_for_ambiguous_page_owner_then_retries_cleanly():
    first = create_identity_user(
        username="first-owner",
        email="first-owner@example.com",
        nickname="First Owner",
        password="owner-passphrase",
        superuser=True,
    )
    second = create_identity_user(
        username="second-owner",
        email="second-owner@example.com",
        nickname="Second Owner",
        password="owner-passphrase",
    )
    _public_post(owner=first, slug="ambiguously-owned")
    second_draft = _draft_post(owner=second, slug="second-author-draft")
    ownerless = _public_post(slug="ambiguous-ownerless")
    MigrationExecutor(connection).migrate([BACKFILL])

    with override_settings(SITE_OWNER_EMAIL="first-owner@example.com"):
        with pytest.raises(RuntimeError, match="activation invariants"):
            MigrationExecutor(connection).migrate([ACTIVATION])

    Page.objects.filter(pk=second_draft.pk).update(owner_id=first.pk)

    with override_settings(SITE_OWNER_EMAIL="first-owner@example.com"):
        executor = MigrationExecutor(connection)
        executor.migrate([ACTIVATION])
    activated_apps = executor.loader.project_state([ACTIVATION]).apps

    assert activated_apps.get_model("users", "User").objects.get(pk=first.pk).is_site_author
    assert Page.objects.get(pk=ownerless.pk).owner_id == first.pk


def test_stage17_activation_accepts_explicit_site_author_when_all_posts_are_owned():
    site_author = create_identity_user(
        username="configured-site-author",
        email="configured-site-author@example.com",
        nickname="Configured Site Author",
        password="owner-passphrase",
        superuser=True,
    )
    guest_author = create_identity_user(
        username="guest-author",
        email="guest-author@example.com",
        nickname="Guest Author",
        password="owner-passphrase",
    )
    site_post = _public_post(owner=site_author, slug="configured-author-post")
    guest_post = _draft_post(owner=guest_author, slug="guest-author-draft")
    MigrationExecutor(connection).migrate([BACKFILL])

    with override_settings(SITE_OWNER_EMAIL="configured-site-author@example.com"):
        executor = MigrationExecutor(connection)
        executor.migrate([ACTIVATION])
    activated_apps = executor.loader.project_state([ACTIVATION]).apps

    assert activated_apps.get_model("users", "User").objects.get(pk=site_author.pk).is_site_author
    assert Page.objects.get(pk=site_post.pk).owner_id == site_author.pk
    assert Page.objects.get(pk=guest_post.pk).owner_id == guest_author.pk


def test_stage17_activation_rejects_runtime_invalid_expansion_identity():
    owner = create_identity_user(
        username="activation-owner",
        email="owner@example.com",
        nickname="Activation Owner",
        password="owner-passphrase",
        superuser=True,
    )
    _public_post(owner=owner, slug="activation-invalid-identity-proof")
    MigrationExecutor(connection).migrate([BACKFILL])

    executor = MigrationExecutor(connection)
    historical_apps = executor.loader.project_state([BACKFILL]).apps
    HistoricalUser = historical_apps.get_model("users", "User")
    HistoricalHistory = historical_apps.get_model("users", "NicknameHistory")
    invalid = HistoricalUser.objects.create(
        username="invalid-expansion-identity",
        email="Reader@Example.com",
        email_normalized="different@example.com",
        nickname="Broken \u0301Mark",
        nickname_normalized="broken \u0301mark",
        nickname_confirmed=True,
    )
    HistoricalHistory.objects.create(
        user_id=invalid.pk,
        nickname=invalid.nickname,
        nickname_normalized=invalid.nickname_normalized,
        change_kind="initial",
        reason="Invalid expansion-window fixture",
    )

    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        with pytest.raises(RuntimeError, match="activation invariants"):
            MigrationExecutor(connection).migrate([ACTIVATION])

    HistoricalHistory.objects.filter(user_id=invalid.pk).delete()
    HistoricalUser.objects.filter(pk=invalid.pk).delete()
    reserved = HistoricalUser.objects.create(
        username="reserved-expansion-identity",
        email="reserved@example.com",
        email_normalized="reserved@example.com",
        nickname="аԁmin",
        nickname_normalized="аԁmin",
        nickname_confirmed=True,
    )
    HistoricalHistory.objects.create(
        user_id=reserved.pk,
        nickname=reserved.nickname,
        nickname_normalized=reserved.nickname_normalized,
        change_kind="initial",
        reason="Reserved expansion-window fixture",
    )

    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        with pytest.raises(RuntimeError, match="activation invariants"):
            MigrationExecutor(connection).migrate([ACTIVATION])

    HistoricalHistory.objects.filter(user_id=reserved.pk).delete()
    HistoricalUser.objects.filter(pk=reserved.pk).delete()
    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        MigrationExecutor(connection).migrate([ACTIVATION])


def test_stage17_activation_rejects_invalid_expansion_window_email():
    owner = create_identity_user(
        username="email-validation-owner",
        email="owner@example.com",
        nickname="Email Validation Owner",
        password="owner-passphrase",
        superuser=True,
    )
    _public_post(owner=owner, slug="activation-invalid-email-proof")
    MigrationExecutor(connection).migrate([BACKFILL])

    historical_apps = MigrationExecutor(connection).loader.project_state([BACKFILL]).apps
    HistoricalUser = historical_apps.get_model("users", "User")
    invalid = HistoricalUser.objects.create(
        username="invalid-expansion-email",
        email="bad address@example.com",
    )

    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        with pytest.raises(RuntimeError, match="valid canonical email"):
            MigrationExecutor(connection).migrate([ACTIVATION])

    HistoricalUser.objects.filter(pk=invalid.pk).delete()
    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        MigrationExecutor(connection).migrate([ACTIVATION])


def test_stage17_activation_rejects_canonical_email_address_ambiguity():
    owner = create_identity_user(
        username="address-ambiguity-owner",
        email="kirill@example.com",
        nickname="Address Ambiguity Owner",
        password="owner-passphrase",
        superuser=True,
    )
    reader = create_identity_user(
        username="address-ambiguity-reader",
        email="reader@example.com",
        nickname="Address Ambiguity Reader",
        password="reader-passphrase",
        verified=False,
    )
    _public_post(owner=owner, slug="activation-address-ambiguity-proof")
    MigrationExecutor(connection).migrate([BACKFILL])
    duplicate = EmailAddress.objects.create(
        user_id=reader.pk,
        email="Kirill@example.com",
        primary=False,
        verified=False,
    )

    with override_settings(SITE_OWNER_EMAIL="kirill@example.com"):
        with pytest.raises(RuntimeError, match="activation invariants"):
            MigrationExecutor(connection).migrate([ACTIVATION])

    duplicate.delete()
    with override_settings(SITE_OWNER_EMAIL="kirill@example.com"):
        MigrationExecutor(connection).migrate([ACTIVATION])


def test_stage17_activation_rejects_missing_claims_and_persisted_social_tokens():
    owner = create_identity_user(
        username="activation-claim-owner",
        email="owner@example.com",
        nickname="Activation Claim Owner",
        password="owner-passphrase",
        superuser=True,
    )
    _public_post(owner=owner, slug="activation-claim-proof")
    MigrationExecutor(connection).migrate([BACKFILL])
    account = SocialAccount.objects.create(
        user_id=owner.pk,
        provider="github",
        uid="activation-token-proof",
    )
    token = SocialToken.objects.create(account=account, token="migration-must-not-accept")
    history = NicknameHistory.objects.get(user_id=owner.pk)
    history_snapshot = {
        "user_id": history.user_id,
        "nickname": history.nickname,
        "nickname_normalized": history.nickname_normalized,
        "change_kind": history.change_kind,
        "reason": history.reason,
    }
    history.delete()

    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        with pytest.raises(RuntimeError, match="activation invariants"):
            MigrationExecutor(connection).migrate([ACTIVATION])

    token.delete()
    NicknameHistory.objects.create(**history_snapshot)
    with override_settings(SITE_OWNER_EMAIL="owner@example.com"):
        MigrationExecutor(connection).migrate([ACTIVATION])
