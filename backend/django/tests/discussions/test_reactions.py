import json
from datetime import timedelta
from urllib.parse import quote

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import PageViewRestriction, Site

from apps.blog.models import BlogPostPage
from apps.discussions.emoji import normalize_emoji
from apps.discussions.models import (
    CommentReaction,
    PostReaction,
    ReactionSettings,
)
from apps.discussions.services import (
    create_reply,
    create_top_level_comment,
    set_comment_hidden,
    soft_delete_comment,
)

pytestmark = pytest.mark.django_db


def post_reactions_url(post):
    return reverse("discussions_api:post-reactions", kwargs={"slug": post.slug})


def post_toggle_url(post):
    return reverse("discussions_api:post-reaction-toggle", kwargs={"slug": post.slug})


def comment_reactions_url(comment):
    return reverse("discussions_api:comment-reactions", kwargs={"pk": comment.pk})


def comment_toggle_url(comment):
    return reverse("discussions_api:comment-reaction-toggle", kwargs={"pk": comment.pk})


def authenticated(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.parametrize(
    "value",
    [
        "🔥",
        "👩‍💻",
        "👍🏽",
        "🇺🇸",
        "1️⃣",
        "♀️",
        "❤️",
        "🏳️‍🌈",
    ],
)
def test_unicode_sequences_are_accepted_and_nfc(value):
    normalized = normalize_emoji(value)
    assert normalized == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        1,
        "",
        "hello",
        "🔥🎉",
        ":fire:",
        " 🔥",
        "🔥\n",
        "🔥\u202e",
        "🏽",
        "👩‍",
        "\ufe0f",
        "\ud800",
        "\udfff",
        "🔥\ud800",
        "👩" * 33,
    ],
)
def test_invalid_or_malformed_reaction_keys_are_rejected(value):
    with pytest.raises(ValidationError):
        normalize_emoji(value)


@pytest.mark.parametrize("value", ["\ud800", "\udfff", "🔥\ud800"])
def test_surrogates_are_safe_across_models_and_wagtail_settings(
    value,
    public_post,
    user,
):
    reaction = PostReaction(post=public_post, user=user, emoji=value)
    with pytest.raises(ValidationError):
        reaction.full_clean()
    with pytest.raises(ValidationError):
        reaction.save()

    site = Site.objects.get(is_default_site=True)
    configured = ReactionSettings.for_site(site)
    configured.quick_reaction_one = value
    with pytest.raises(ValidationError):
        configured.full_clean()
    with pytest.raises(ValidationError):
        configured.save()


@pytest.mark.parametrize("value", ["\ud800", "\udfff", "🔥\ud800"])
def test_toggle_rejects_raw_json_surrogates_without_html_500(
    value,
    public_post,
    user,
):
    client = authenticated(user)
    payload = json.dumps({"emoji": value})

    response = client.post(
        post_toggle_url(public_post),
        data=payload,
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response["Content-Type"].startswith("application/json")
    assert response.data == {
        "emoji": ["Emoji contains whitespace or a forbidden control character."]
    }
    assert not PostReaction.objects.filter(post=public_post, user=user).exists()


def test_concrete_reaction_uniqueness_normalization_and_protected_relations(
    public_post, user, other_user
):
    comment = create_top_level_comment(post=public_post, author=user, body="Root")
    post_reaction = PostReaction.objects.create(post=public_post, user=user, emoji="🔥")
    comment_reaction = CommentReaction.objects.create(comment=comment, user=user, emoji="👩‍💻")
    PostReaction.objects.create(post=public_post, user=user, emoji="🎉")
    PostReaction.objects.create(post=public_post, user=other_user, emoji="🔥")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PostReaction.objects.create(post=public_post, user=user, emoji="🔥")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CommentReaction.objects.create(comment=comment, user=user, emoji="👩‍💻")

    assert post_reaction.emoji == "🔥"
    assert comment_reaction.emoji == "👩‍💻"
    with pytest.raises(ProtectedError):
        user.delete()
    with pytest.raises(ProtectedError):
        comment.delete()


def test_post_toggle_add_remove_multiple_groups_and_anonymous_read(public_post, user, other_user):
    first = authenticated(user).post(post_toggle_url(public_post), {"emoji": "🔥"}, format="json")
    second = authenticated(user).post(post_toggle_url(public_post), {"emoji": "🎉"}, format="json")
    authenticated(other_user).post(post_toggle_url(public_post), {"emoji": "🔥"}, format="json")
    listing = APIClient().get(post_reactions_url(public_post))
    removed = authenticated(user).post(post_toggle_url(public_post), {"emoji": "🔥"}, format="json")

    assert first.status_code == 200
    assert first.data["action"] == "added"
    assert second.data["action"] == "added"
    assert listing.status_code == 200
    assert listing["Cache-Control"] == "private, no-store"
    assert "Cookie" in listing["Vary"]
    assert listing.data["reactions"] == [
        {
            "emoji": "🎉",
            "count": 1,
            "viewer_reacted": False,
            "participants": (
                f"/api/v1/posts/{quote(public_post.slug)}/reactions/%F0%9F%8E%89/participants/"
            ),
        },
        {
            "emoji": "🔥",
            "count": 2,
            "viewer_reacted": False,
            "participants": (
                f"/api/v1/posts/{quote(public_post.slug)}/reactions/%F0%9F%94%A5/participants/"
            ),
        },
    ]
    assert removed.data["action"] == "removed"
    assert removed.data["reactions"][1]["count"] == 1
    assert PostReaction.objects.filter(post=public_post, user=user, emoji="🔥").count() == 0


def test_toggle_payload_authentication_activity_and_csrf(public_post, user, other_user):
    url = post_toggle_url(public_post)
    assert APIClient().post(url, {"emoji": "🔥"}, format="json").status_code == 403
    assert (
        authenticated(user)
        .post(url, {"emoji": "🔥", "user": other_user.pk}, format="json")
        .status_code
        == 400
    )

    user.is_banned = True
    user.save(update_fields=("is_banned",))
    assert authenticated(user).post(url, {"emoji": "🔥"}, format="json").status_code == 403
    user.is_banned = False
    user.is_active = False
    user.save(update_fields=("is_banned", "is_active"))
    assert authenticated(user).post(url, {"emoji": "🔥"}, format="json").status_code == 403

    user.is_active = True
    user.save(update_fields=("is_active",))
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    assert (
        csrf_client.post(url, {"emoji": "🔥"}, content_type="application/json").status_code == 403
    )
    token = csrf_client.get("/api/me/").json()["csrf_token"]
    assert (
        csrf_client.post(
            url,
            {"emoji": "🔥"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        == 200
    )


def test_post_reactions_reuse_public_visibility_policy(blog_index, public_post, user):
    now = timezone.now()
    states = []
    for slug in ("draft-react", "future-react", "expired-react", "restricted-react"):
        post = BlogPostPage(
            title=slug,
            slug=slug,
            excerpt="Unavailable.",
            body=[("rich_text", "<p>Body.</p>")],
            live=False,
        )
        blog_index.add_child(instance=post)
        if slug != "draft-react":
            post.save_revision().publish()
            post = BlogPostPage.objects.get(pk=post.pk)
        if slug == "future-react":
            BlogPostPage.objects.filter(pk=post.pk).update(go_live_at=now + timedelta(hours=1))
        elif slug == "expired-react":
            BlogPostPage.objects.filter(pk=post.pk).update(expire_at=now - timedelta(seconds=1))
        elif slug == "restricted-react":
            PageViewRestriction.objects.create(
                page=post,
                restriction_type=PageViewRestriction.PASSWORD,
                password="test-only",
            )
        states.append(post)

    assert APIClient().get(post_reactions_url(public_post)).status_code == 200
    for post in states:
        assert APIClient().get(post_reactions_url(post)).status_code == 404
        assert (
            authenticated(user)
            .post(post_toggle_url(post), {"emoji": "🔥"}, format="json")
            .status_code
            == 404
        )


def test_comment_and_reply_reactions_are_batched_and_tombstones_are_private(
    public_post, user, other_user, admin_user
):
    roots = [
        create_top_level_comment(post=public_post, author=user, body=f"Root {index}")
        for index in range(20)
    ]
    reply = create_reply(target_id=roots[0].pk, author=other_user, body="Reply")
    PostReaction.objects.create(post=public_post, user=user, emoji="🔥")
    for comment in [*roots, reply]:
        CommentReaction.objects.create(comment=comment, user=user, emoji="🔥")

    with CaptureQueriesContext(connection) as queries:
        listing = authenticated(user).get(
            reverse("discussions_api:post-comments", kwargs={"slug": public_post.slug})
        )
    assert len(queries) <= 7
    assert all(item["reactions"][0]["viewer_reacted"] for item in listing.data["results"])

    thread = authenticated(user).get(
        reverse("discussions_api:comment-thread", kwargs={"pk": roots[0].pk})
    )
    assert thread.data["root"]["reactions"][0]["count"] == 1
    assert thread.data["results"][0]["reactions"][0]["count"] == 1

    soft_delete_comment(comment_id=roots[1].pk, actor=user)
    set_comment_hidden(comment_id=roots[2].pk, moderator=admin_user, hidden=True)
    for comment in roots[1:3]:
        assert APIClient().get(comment_reactions_url(comment)).data["reactions"] == []
        assert (
            authenticated(other_user)
            .post(comment_toggle_url(comment), {"emoji": "🎉"}, format="json")
            .status_code
            == 403
        )
        participants = reverse(
            "discussions_api:comment-reaction-participants",
            kwargs={"pk": comment.pk, "emoji": "🔥"},
        )
        assert APIClient().get(participants).status_code == 404
        assert CommentReaction.objects.filter(comment=comment, emoji="🔥").exists()


def test_participants_are_minimal_cursor_paginated_and_endpoint_bound(public_post, user):
    users = [user]
    for index in range(20):
        users.append(
            get_user_model().objects.create_user(
                username=f"participant-{index}",
                email=f"participant-{index}@example.com",
                password="test",
            )
        )
    for participant in users:
        PostReaction.objects.create(post=public_post, user=participant, emoji="🔥")

    group = APIClient().get(post_reactions_url(public_post)).data["reactions"][0]
    first = APIClient().get(group["participants"])
    second = APIClient().get(first.data["next"])

    assert len(first.data["results"]) == 20
    assert len(second.data["results"]) == 1
    assert first.data["next"].startswith("/api/v1/posts/")
    assert "testserver" not in first.data["next"]
    assert set(first.data["results"][0]) == {"id", "display_name", "is_site_author"}
    assert "email" not in str(first.data).lower()


@override_settings(
    REACTION_TOGGLE_RATE_LIMIT_COUNT=1,
    REACTION_TOGGLE_RATE_LIMIT_WINDOW_SECONDS=60,
)
def test_reaction_rate_limit_retry_after(public_post, user):
    client = authenticated(user)
    first = client.post(post_toggle_url(public_post), {"emoji": "🔥"}, format="json")
    second = client.post(post_toggle_url(public_post), {"emoji": "🎉"}, format="json")

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second["Retry-After"]) >= 1
    assert user.reaction_rate_limit_bucket.request_count == 1


def test_quick_reaction_settings_normalize_validate_uniqueness_and_public_contract(
    public_post,
):
    site = Site.objects.get(is_default_site=True)
    configured = ReactionSettings.for_site(site)
    configured.quick_reaction_one = "👩‍💻"
    configured.quick_reaction_two = "👍🏽"
    configured.quick_reaction_three = "🇺🇸"
    configured.full_clean()
    configured.save()

    response = APIClient().get(reverse("discussions_api:reaction-config"))

    assert response.status_code == 200
    assert response.data == {"quick_reactions": ["👩‍💻", "👍🏽", "🇺🇸"]}
    assert set(response.data) == {"quick_reactions"}

    configured.quick_reaction_three = "👩‍💻"
    with pytest.raises(ValidationError):
        configured.full_clean()
