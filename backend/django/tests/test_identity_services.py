from unittest.mock import patch

import pytest
from allauth.account.models import EmailAddress
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from wagtail.models import Locale, Page

from apps.blog.models import BlogIndexPage, BlogPostPage, RevalidationEvent
from apps.users.models import NicknameHistory, User
from apps.users.services import (
    IdentityInvariantError,
    can_interact,
    change_nickname,
    nickname_change_available_at,
    normalize_public_nickname,
    public_display_name,
)
from tests.identity import create_identity_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def identity_blog_index():
    locale, _ = Locale.objects.get_or_create(language_code="en")
    root = Page.get_first_root_node()
    if root is None:
        root = Page.add_root(instance=Page(title="Root", slug="root", locale=locale))
    index = BlogIndexPage(title="Identity service", slug="identity-service", live=False)
    root.add_child(instance=index)
    return index


def test_public_display_name_has_no_runtime_username_or_full_name_fallback():
    user = User.objects.create_user(
        username="legacy-visible-name",
        email="reader@example.com",
        first_name="Legacy",
        last_name="Full Name",
    )

    with pytest.raises(IdentityInvariantError):
        public_display_name(user)


def test_database_rejects_incoherent_rollout_identity_and_multiple_site_authors():
    first = create_identity_user(
        username="first-author",
        email="first-author@example.com",
        nickname="First Author",
        site_author=True,
    )
    second = create_identity_user(
        username="second-author",
        email="second-author@example.com",
        nickname="Second Author",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=second.pk).update(
            nickname=None,
            nickname_normalized="orphaned-key",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=second.pk).update(is_site_author=True)

    assert User.objects.get(pk=first.pk).is_site_author is True
    assert User.objects.get(pk=second.pk).is_site_author is False


def test_can_interact_requires_every_identity_and_availability_boundary():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
    )
    assert can_interact(user) is True

    EmailAddress.objects.filter(user=user, primary=True).update(verified=False)
    user = User.objects.get(pk=user.pk)
    assert can_interact(user) is False

    EmailAddress.objects.filter(user=user, primary=True).update(verified=True)
    User.objects.filter(pk=user.pk).update(nickname_confirmed=False)
    user = User.objects.get(pk=user.pk)
    assert can_interact(user) is False

    User.objects.filter(pk=user.pk).update(nickname_confirmed=True, is_banned=True)
    user = User.objects.get(pk=user.pk)
    assert can_interact(user) is False

    User.objects.filter(pk=user.pk).update(is_banned=False, is_active=False)
    user = User.objects.get(pk=user.pk)
    assert can_interact(user) is False


def test_marked_site_owner_nickname_is_reserved_against_impersonation():
    owner = create_identity_user(
        username="owner",
        email="owner@example.com",
        nickname="Kirill Wynn",
        superuser=True,
        site_author=True,
    )
    reader = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
    )

    with pytest.raises(ValidationError):
        normalize_public_nickname("Kírill-Wynn", user=reader)

    assert normalize_public_nickname("Kirill Wynn", user=owner).display == "Kirill Wynn"


def test_user_rename_is_blocked_for_unavailable_account_and_reports_exact_cooldown():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        is_banned=True,
    )
    with pytest.raises(PermissionDenied):
        change_nickname(user=user, nickname="Unavailable Reader")

    User.objects.filter(pk=user.pk).update(is_banned=False)
    user.refresh_from_db()
    changed = change_nickname(user=user, nickname="Available Reader")
    available_at = nickname_change_available_at(changed)
    assert available_at is not None
    assert available_at > timezone.now()

    with pytest.raises(ValidationError) as error:
        change_nickname(user=changed, nickname="Again Too Soon")
    assert error.value.message_dict["nickname_change_available_at"] == [available_at.isoformat()]


def test_staff_override_bypasses_cooldown_only_with_actor_reason_and_audit():
    actor = create_identity_user(
        username="moderator",
        email="moderator@example.com",
        nickname="Moderator Person",
        is_staff=True,
    )
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
    )
    user = change_nickname(user=user, nickname="Recent Reader")
    unavailable = create_identity_user(
        username="unavailable-reader",
        email="unavailable@example.com",
        nickname="Unavailable Reader",
        is_banned=True,
    )

    with pytest.raises(PermissionDenied):
        change_nickname(
            user=unavailable,
            nickname="Staff Cannot Rename This",
            actor=actor,
            staff_override=True,
            reason="The availability boundary must still win",
        )
    assert not NicknameHistory.objects.filter(
        user=unavailable,
        change_kind=NicknameHistory.ChangeKind.STAFF_OVERRIDE,
    ).exists()

    with pytest.raises(ValidationError):
        change_nickname(
            user=user,
            nickname="Admin",
            actor=actor,
            staff_override=True,
            reason="",
        )
    changed = change_nickname(
        user=user,
        nickname="Admin",
        actor=actor,
        staff_override=True,
        reason="Documented impersonation exception",
    )
    audit = NicknameHistory.objects.get(
        user=user,
        change_kind=NicknameHistory.ChangeKind.STAFF_OVERRIDE,
    )

    assert changed.nickname == "Admin"
    assert audit.actor_id == actor.pk
    assert audit.reason == "Documented impersonation exception"


def test_staff_public_profile_cannot_bypass_reserved_name_audit():
    staff = create_identity_user(
        username="staff-reader",
        email="staff-reader@example.com",
        nickname="Staff Person",
        is_staff=True,
    )

    with pytest.raises(ValidationError, match="reserved"):
        change_nickname(user=staff, nickname="Admin")


def test_author_rename_queues_each_owned_post_revalidation_after_commit(
    identity_blog_index,
    django_capture_on_commit_callbacks,
    settings,
):
    author = create_identity_user(
        username="author",
        email="author@example.com",
        nickname="Original Author",
    )
    posts = []
    for index in range(2):
        post = BlogPostPage(
            title=f"Owned post {index}",
            slug=f"owned-post-{index}",
            excerpt="Owned post.",
            body=[("rich_text", "<p>Owned post.</p>")],
            owner=author,
            live=False,
        )
        identity_blog_index.add_child(instance=post)
        post.save_revision().publish()
        posts.append(post)
    draft = BlogPostPage(
        title="Private draft",
        slug="private-draft",
        excerpt="Private draft.",
        body=[("rich_text", "<p>Private draft.</p>")],
        owner=author,
        live=False,
    )
    identity_blog_index.add_child(instance=draft)
    draft.save_revision()
    settings.REVALIDATION_URL = "http://next.test/api/revalidate"

    with patch("apps.blog.services.revalidation.deliver_event") as deliver:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            change_nickname(user=author, nickname="Current Author")
            assert deliver.call_count == 0
        assert len(callbacks) == 2

    assert deliver.call_count == 2
    assert set(RevalidationEvent.objects.values_list("page_id", flat=True)) == {
        post.pk for post in posts
    }
    assert not RevalidationEvent.objects.filter(page_id=draft.pk).exists()
