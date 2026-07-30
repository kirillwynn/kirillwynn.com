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


def post_reaction_batch_url():
    return reverse("discussions_api:post-reaction-batch")


def comment_reactions_url(comment):
    return reverse("discussions_api:comment-reactions", kwargs={"pk": comment.pk})


def comment_toggle_url(comment):
    return reverse("discussions_api:comment-reaction-toggle", kwargs={"pk": comment.pk})


def authenticated(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def publish_post(blog_index, slug):
    post = BlogPostPage(
        title=slug,
        slug=slug,
        excerpt=f"Excerpt for {slug}.",
        body=[("rich_text", "<p>Body.</p>")],
        live=False,
    )
    blog_index.add_child(instance=post)
    post.save_revision().publish()
    return BlogPostPage.objects.get(pk=post.pk)


def expected_descriptor(item):
    asset_url = f"/media/{item.asset_storage_key}"
    return {
        "id": item.catalog_id,
        "name": item.display_name,
        "label": item.accessibility_label,
        "kind": item.kind,
        "asset_url": asset_url,
        "poster_url": (
            f"/media/{item.poster_storage_key}" if item.poster_storage_key else asset_url
        ),
        "width": item.intrinsic_width,
        "height": item.intrinsic_height,
        "version": item.immutable_asset_version,
    }


def expected_group(item, *, count, viewer_reacted, participants):
    return {
        "reaction": expected_descriptor(item),
        "count": count,
        "viewer_reacted": viewer_reacted,
        "participants": participants,
    }


def test_legacy_unicode_rows_remain_reversible_but_are_read_only_and_hidden(
    public_post,
    user,
):
    comment = create_top_level_comment(post=public_post, author=user, body="Root")
    PostReaction.objects.bulk_create([PostReaction(post=public_post, user=user, emoji="🔥")])
    CommentReaction.objects.bulk_create([CommentReaction(comment=comment, user=user, emoji="👩‍💻")])
    post_reaction = PostReaction.objects.get(post=public_post, user=user)
    comment_reaction = CommentReaction.objects.get(comment=comment, user=user)

    assert APIClient().get(post_reactions_url(public_post)).data == {"reactions": []}
    assert APIClient().get(comment_reactions_url(comment)).data == {"reactions": []}
    assert (post_reaction.emoji, post_reaction.catalog_item_id) == ("🔥", None)
    assert (comment_reaction.emoji, comment_reaction.catalog_item_id) == ("👩‍💻", None)

    post_reaction.save(update_fields=("emoji",))
    with pytest.raises(ValidationError, match="read-only"):
        PostReaction(post=public_post, user=user, emoji="🎉").save()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PostReaction.objects.bulk_create(
                [PostReaction(post=public_post, user=user, emoji="🔥")]
            )


def test_catalog_reaction_uniqueness_and_protected_relations(
    public_post,
    user,
    other_user,
    reaction_catalog_items,
):
    first_item, second_item, _ = reaction_catalog_items
    comment = create_top_level_comment(post=public_post, author=user, body="Root")
    post_reaction = PostReaction.objects.create(
        post=public_post,
        user=user,
        catalog_item=first_item,
    )
    comment_reaction = CommentReaction.objects.create(
        comment=comment,
        user=user,
        catalog_item=first_item,
    )
    PostReaction.objects.create(
        post=public_post,
        user=user,
        catalog_item=second_item,
    )
    PostReaction.objects.create(
        post=public_post,
        user=other_user,
        catalog_item=first_item,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PostReaction.objects.create(
                post=public_post,
                user=user,
                catalog_item=first_item,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CommentReaction.objects.create(
                comment=comment,
                user=user,
                catalog_item=first_item,
            )

    assert post_reaction.emoji == ""
    assert comment_reaction.emoji == ""
    with pytest.raises(ProtectedError):
        first_item.delete()
    with pytest.raises(ProtectedError):
        user.delete()
    with pytest.raises(ProtectedError):
        comment.delete()


def test_post_toggle_add_remove_multiple_groups_and_anonymous_read(
    public_post,
    user,
    other_user,
    reaction_catalog_items,
):
    first_item, second_item, _ = reaction_catalog_items
    first = authenticated(user).post(
        post_toggle_url(public_post),
        {"reaction_id": first_item.catalog_id},
        format="json",
    )
    second = authenticated(user).post(
        post_toggle_url(public_post),
        {"reaction_id": second_item.catalog_id},
        format="json",
    )
    authenticated(other_user).post(
        post_toggle_url(public_post),
        {"reaction_id": first_item.catalog_id},
        format="json",
    )
    listing = APIClient().get(post_reactions_url(public_post))
    removed = authenticated(user).post(
        post_toggle_url(public_post),
        {"reaction_id": first_item.catalog_id},
        format="json",
    )

    assert first.status_code == 200
    assert first.data["action"] == "added"
    assert second.data["action"] == "added"
    assert listing.status_code == 200
    assert listing["Cache-Control"] == "private, no-store"
    assert "Cookie" in listing["Vary"]
    assert listing.data["reactions"] == [
        expected_group(
            first_item,
            count=2,
            viewer_reacted=False,
            participants=(
                f"/api/v1/posts/{quote(public_post.slug)}/reactions/"
                f"{first_item.catalog_id}/participants/"
            ),
        ),
        expected_group(
            second_item,
            count=1,
            viewer_reacted=False,
            participants=(
                f"/api/v1/posts/{quote(public_post.slug)}/reactions/"
                f"{second_item.catalog_id}/participants/"
            ),
        ),
    ]
    assert removed.data["action"] == "removed"
    assert removed.data["reactions"][0]["count"] == 1
    assert (
        PostReaction.objects.filter(
            post=public_post,
            user=user,
            catalog_item=first_item,
        ).count()
        == 0
    )


def test_post_reaction_batch_requires_one_strict_bounded_unique_ids_parameter(public_post):
    client = APIClient()
    url = post_reaction_batch_url()

    missing = client.get(url)
    repeated = client.get(f"{url}?ids={public_post.pk}&ids={public_post.pk + 1}")
    assert missing.status_code == 400
    assert repeated.status_code == 400
    assert missing.data == {"ids": ["This parameter must be provided exactly once."]}
    assert repeated.data == missing.data

    malformed_values = (
        "",
        "0",
        "-1",
        "+1",
        "01",
        "1.0",
        "1,,2",
        " 1",
        "1 ",
        "9223372036854775808",
    )
    for value in malformed_values:
        response = client.get(url, {"ids": value})
        assert response.status_code == 400
        assert response.data == {
            "ids": ["This parameter must be a comma-separated list of positive integers."]
        }

    duplicate = client.get(url, {"ids": f"{public_post.pk},{public_post.pk}"})
    assert duplicate.status_code == 400
    assert duplicate.data == {"ids": ["IDs must be unique."]}

    oversized = client.get(
        url,
        {"ids": ",".join(str(value) for value in range(1, 52))},
    )
    assert oversized.status_code == 400
    assert oversized.data == {"ids": ["At most 50 IDs may be requested."]}

    unexpected = client.get(url, {"ids": str(public_post.pk), "cursor": "nope"})
    assert unexpected.status_code == 400
    assert unexpected.data == {"detail": "Unexpected query parameter(s): cursor."}

    for response in (missing, repeated, duplicate, oversized, unexpected):
        assert response["Content-Type"].startswith("application/json")
        assert response["Cache-Control"] == "private, no-store"
        assert "Cookie" in response["Vary"]


def test_post_reaction_batch_returns_deterministic_groups_and_viewer_state(
    blog_index,
    public_post,
    user,
    other_user,
    reaction_catalog_items,
):
    first_item, second_item, _ = reaction_catalog_items
    second = publish_post(blog_index, "batch-second")
    PostReaction.objects.create(
        post=public_post,
        user=user,
        catalog_item=first_item,
    )
    PostReaction.objects.create(
        post=public_post,
        user=other_user,
        catalog_item=first_item,
    )
    PostReaction.objects.create(
        post=public_post,
        user=other_user,
        catalog_item=second_item,
    )
    requested = f"{second.pk},{public_post.pk},9223372036854775807"

    anonymous = APIClient().get(post_reaction_batch_url(), {"ids": requested})
    session_client = Client()
    session_client.force_login(user)
    signed_in = session_client.get(
        post_reaction_batch_url(),
        {"ids": requested},
    )

    assert anonymous.status_code == 200
    assert anonymous["Cache-Control"] == "private, no-store"
    assert "Cookie" in anonymous["Vary"]
    assert [item["post_id"] for item in anonymous.data["results"]] == [
        second.pk,
        public_post.pk,
    ]
    assert anonymous.data["results"][0] == {
        "post_id": second.pk,
        "slug": second.slug,
        "reactions": [],
    }
    assert anonymous.data["results"][1]["slug"] == "привет-мир"
    assert anonymous.data["results"][1]["reactions"] == [
        expected_group(
            first_item,
            count=2,
            viewer_reacted=False,
            participants=(
                "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-"
                f"%D0%BC%D0%B8%D1%80/reactions/{first_item.catalog_id}/participants/"
            ),
        ),
        expected_group(
            second_item,
            count=1,
            viewer_reacted=False,
            participants=(
                "/api/v1/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-"
                f"%D0%BC%D0%B8%D1%80/reactions/{second_item.catalog_id}/participants/"
            ),
        ),
    ]
    assert [group["viewer_reacted"] for group in signed_in.json()["results"][1]["reactions"]] == [
        True,
        False,
    ]


def test_post_reaction_batch_omits_every_non_public_visibility_state(
    blog_index,
    public_post,
    user,
    reaction_catalog_item,
):
    now = timezone.now()
    draft = BlogPostPage(
        title="batch-draft",
        slug="batch-draft",
        excerpt="Draft.",
        body=[("rich_text", "<p>Body.</p>")],
        live=False,
    )
    blog_index.add_child(instance=draft)

    scheduled = publish_post(blog_index, "batch-scheduled")
    BlogPostPage.objects.filter(pk=scheduled.pk).update(go_live_at=now + timedelta(hours=1))
    expired = publish_post(blog_index, "batch-expired")
    BlogPostPage.objects.filter(pk=expired.pk).update(expire_at=now - timedelta(seconds=1))
    unpublished = publish_post(blog_index, "batch-unpublished")
    unpublished.unpublish()
    restricted = publish_post(blog_index, "batch-restricted")
    PageViewRestriction.objects.create(
        page=restricted,
        restriction_type=PageViewRestriction.PASSWORD,
        password="test-only",
    )
    hidden_posts = [draft, scheduled, expired, unpublished, restricted]
    for post in hidden_posts:
        PostReaction.objects.create(
            post=post,
            user=user,
            catalog_item=reaction_catalog_item,
        )

    response = APIClient().get(
        post_reaction_batch_url(),
        {
            "ids": ",".join(
                str(post_id)
                for post_id in [
                    hidden_posts[0].pk,
                    public_post.pk,
                    *(post.pk for post in hidden_posts[1:]),
                    9_223_372_036_854_775_807,
                ]
            )
        },
    )

    assert response.status_code == 200
    assert response.data["results"] == [
        {
            "post_id": public_post.pk,
            "slug": public_post.slug,
            "reactions": [],
        }
    ]


def test_post_reaction_batch_query_count_is_bounded(
    blog_index,
    public_post,
    user,
    reaction_catalog_item,
):
    posts = [public_post]
    for index in range(11):
        posts.append(publish_post(blog_index, f"batch-query-{index}"))
    for post in posts:
        PostReaction.objects.create(
            post=post,
            user=user,
            catalog_item=reaction_catalog_item,
        )

    with CaptureQueriesContext(connection) as queries:
        response = authenticated(user).get(
            post_reaction_batch_url(),
            {"ids": ",".join(str(post.pk) for post in reversed(posts))},
        )

    assert response.status_code == 200
    assert len(response.data["results"]) == len(posts)
    assert len(queries) <= 4


def test_toggle_payload_authentication_activity_and_csrf(
    public_post,
    user,
    other_user,
    reaction_catalog_item,
):
    url = post_toggle_url(public_post)
    payload = {"reaction_id": reaction_catalog_item.catalog_id}
    assert APIClient().post(url, payload, format="json").status_code == 403
    assert (
        authenticated(user)
        .post(
            url,
            {"reaction_id": reaction_catalog_item.catalog_id, "user": other_user.pk},
            format="json",
        )
        .status_code
        == 400
    )

    user.is_banned = True
    user.save(update_fields=("is_banned",))
    assert authenticated(user).post(url, payload, format="json").status_code == 403
    user.is_banned = False
    user.is_active = False
    user.save(update_fields=("is_banned", "is_active"))
    assert authenticated(user).post(url, payload, format="json").status_code == 403

    user.is_active = True
    user.save(update_fields=("is_active",))
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    assert csrf_client.post(url, payload, content_type="application/json").status_code == 403
    token = csrf_client.get("/api/me/").json()["csrf_token"]
    assert (
        csrf_client.post(
            url,
            payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"emoji": "🔥"},
        {"reaction_id": "🔥"},
        {"reaction_id": ":pepeclap:"},
        {"reaction_id": "pepeclap.png"},
        {"reaction_id": "https://media.example/reaction.gif"},
        {"reaction_id": "../pepeclap"},
        {"reaction_id": ""},
        {"reaction_id": None},
        {"reaction_id": {"id": "pepeclap"}},
    ],
)
def test_toggle_rejects_unicode_unknown_or_non_catalog_identity(
    payload,
    public_post,
    user,
):
    response = authenticated(user).post(
        post_toggle_url(public_post),
        payload,
        format="json",
    )

    assert response.status_code == 400
    assert not PostReaction.objects.filter(post=public_post, user=user).exists()


def test_toggle_rejects_unknown_and_disabled_catalog_items(
    public_post,
    user,
    reaction_catalog_items,
):
    disabled = reaction_catalog_items[-1]
    type(disabled).objects.filter(pk=disabled.pk).update(
        enabled=False,
        selectable=False,
        quick_order=None,
    )
    client = authenticated(user)

    unknown = client.post(
        post_toggle_url(public_post),
        {"reaction_id": "not-in-the-catalog"},
        format="json",
    )
    unavailable = client.post(
        post_toggle_url(public_post),
        {"reaction_id": disabled.catalog_id},
        format="json",
    )

    assert unknown.status_code == unavailable.status_code == 400
    assert not PostReaction.objects.filter(post=public_post, user=user).exists()


def test_post_reactions_reuse_public_visibility_policy(
    blog_index,
    public_post,
    user,
    reaction_catalog_item,
):
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
            .post(
                post_toggle_url(post),
                {"reaction_id": reaction_catalog_item.catalog_id},
                format="json",
            )
            .status_code
            == 404
        )


def test_comment_and_reply_reactions_are_batched_and_tombstones_are_private(
    public_post,
    user,
    other_user,
    admin_user,
    reaction_catalog_items,
):
    first_item, second_item, _ = reaction_catalog_items
    roots = [
        create_top_level_comment(post=public_post, author=user, body=f"Root {index}")
        for index in range(20)
    ]
    reply = create_reply(target_id=roots[0].pk, author=other_user, body="Reply")
    PostReaction.objects.create(
        post=public_post,
        user=user,
        catalog_item=first_item,
    )
    for comment in [*roots, reply]:
        CommentReaction.objects.create(
            comment=comment,
            user=user,
            catalog_item=first_item,
        )

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
            .post(
                comment_toggle_url(comment),
                {"reaction_id": second_item.catalog_id},
                format="json",
            )
            .status_code
            == 403
        )
        participants = reverse(
            "discussions_api:comment-reaction-participants",
            kwargs={"pk": comment.pk, "reaction_id": first_item.catalog_id},
        )
        assert APIClient().get(participants).status_code == 404
        assert CommentReaction.objects.filter(
            comment=comment,
            catalog_item=first_item,
        ).exists()


def test_participants_are_minimal_cursor_paginated_and_endpoint_bound(
    public_post,
    user,
    reaction_catalog_item,
):
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
        PostReaction.objects.create(
            post=public_post,
            user=participant,
            catalog_item=reaction_catalog_item,
        )

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
def test_reaction_rate_limit_retry_after(
    public_post,
    user,
    reaction_catalog_items,
):
    first_item, second_item, _ = reaction_catalog_items
    client = authenticated(user)
    first = client.post(
        post_toggle_url(public_post),
        {"reaction_id": first_item.catalog_id},
        format="json",
    )
    second = client.post(
        post_toggle_url(public_post),
        {"reaction_id": second_item.catalog_id},
        format="json",
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second["Retry-After"]) >= 1
    assert user.reaction_rate_limit_bucket.request_count == 1


def test_catalog_and_quick_config_are_public_cached_user_independent_contracts(
    reaction_catalog_items,
):
    site = Site.objects.get(is_default_site=True)
    configured = ReactionSettings.for_site(site)
    configured.quick_reaction_item_one = reaction_catalog_items[0]
    configured.quick_reaction_item_two = reaction_catalog_items[1]
    configured.quick_reaction_item_three = reaction_catalog_items[2]
    configured.full_clean()
    configured.save()

    client = APIClient()
    config = client.get(reverse("discussions_api:reaction-config"))
    catalog = client.get(reverse("discussions_api:reaction-catalog"))

    assert config.status_code == catalog.status_code == 200
    assert config.data == {
        "quick_reactions": [expected_descriptor(item) for item in reaction_catalog_items]
    }
    assert catalog.data["results"] == [expected_descriptor(item) for item in reaction_catalog_items]
    assert catalog.data["version"].startswith("sha256-")
    for response in (config, catalog):
        assert response["Cache-Control"] == ("public, max-age=60, stale-while-revalidate=300")
        assert "cookie" not in response.get("Vary", "").lower()
        assert response["ETag"].startswith('"')

    not_modified = client.get(
        reverse("discussions_api:reaction-catalog"),
        HTTP_IF_NONE_MATCH=catalog["ETag"],
    )
    assert not_modified.status_code == 304
    assert not_modified["ETag"] == catalog["ETag"]

    configured.quick_reaction_item_three = reaction_catalog_items[0]
    with pytest.raises(ValidationError):
        configured.full_clean()


def test_disabled_catalog_item_is_absent_from_catalog_groups_and_participants(
    public_post,
    user,
    reaction_catalog_items,
):
    item = reaction_catalog_items[0]
    PostReaction.objects.create(
        post=public_post,
        user=user,
        catalog_item=item,
    )
    type(item).objects.filter(pk=item.pk).update(
        enabled=False,
        selectable=False,
        quick_order=None,
    )

    assert APIClient().get(post_reactions_url(public_post)).data == {"reactions": []}
    catalog = APIClient().get(reverse("discussions_api:reaction-catalog"))
    assert item.catalog_id not in [entry["id"] for entry in catalog.data["results"]]
    participants = reverse(
        "discussions_api:post-reaction-participants",
        kwargs={"slug": public_post.slug, "reaction_id": item.catalog_id},
    )
    assert APIClient().get(participants).status_code == 404
    assert PostReaction.objects.filter(catalog_item=item).exists()
