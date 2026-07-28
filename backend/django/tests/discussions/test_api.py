from datetime import timedelta

import pytest
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import PageViewRestriction

from apps.blog.models import BlogPostPage
from apps.discussions.services import (
    create_reply,
    create_top_level_comment,
    set_comment_hidden,
    soft_delete_comment,
)

pytestmark = pytest.mark.django_db


def comments_url(post):
    return reverse("discussions_api:post-comments", kwargs={"slug": post.slug})


def login_api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_anonymous_list_contract_plain_text_headers_and_no_n_plus_one(
    public_post, user, other_user
):
    root = create_top_level_comment(
        post=public_post,
        author=user,
        body='<script>alert("text only")</script>',
    )
    create_reply(target_id=root.pk, author=other_user, body="Reply")
    client = APIClient()

    with CaptureQueriesContext(connection) as queries:
        response = client.get(comments_url(public_post))

    assert response.status_code == 200
    assert len(queries) <= 5
    assert response["Cache-Control"] == "private, no-store"
    assert "Cookie" in response["Vary"]
    result = response.data["results"][0]
    assert set(result) == {
        "id",
        "kind",
        "body",
        "status",
        "author",
        "thread_root_id",
        "reply_to",
        "created_at",
        "updated_at",
        "edited_at",
        "reply_count",
        "last_reply_at",
        "reactions",
        "viewer",
    }
    assert result["body"] == '<script>alert("text only")</script>'
    assert result["author"] == {
        "id": user.pk,
        "display_name": "Safe Reader",
        "is_site_author": False,
    }
    assert "email" not in str(response.data).lower()
    assert result["reply_count"] == 1
    assert result["last_reply_at"] is not None
    assert result["viewer"] == {
        "can_edit": False,
        "can_delete": False,
        "can_reply": False,
        "can_react": False,
    }


def test_comment_visibility_reuses_public_post_policy(blog_index, public_post):
    now = timezone.now()
    states = []
    for slug in ("draft", "unpublished", "future", "expired", "restricted"):
        post = BlogPostPage(
            title=slug.title(),
            slug=slug,
            excerpt="Not public.",
            body=[("rich_text", "<p>Body.</p>")],
            live=False,
        )
        blog_index.add_child(instance=post)
        if slug != "draft":
            post.save_revision().publish()
            post = BlogPostPage.objects.get(pk=post.pk)
        if slug == "unpublished":
            post.unpublish()
        elif slug == "future":
            BlogPostPage.objects.filter(pk=post.pk).update(go_live_at=now + timedelta(hours=1))
        elif slug == "expired":
            BlogPostPage.objects.filter(pk=post.pk).update(expire_at=now - timedelta(seconds=1))
        elif slug == "restricted":
            PageViewRestriction.objects.create(
                page=post,
                restriction_type=PageViewRestriction.PASSWORD,
                password="test-only",
            )
        states.append(post)

    assert APIClient().get(comments_url(public_post)).status_code == 200
    for post in states:
        assert APIClient().get(comments_url(post)).status_code == 404


def test_create_requires_session_csrf_and_rejects_identity_fields(public_post, user):
    anonymous = APIClient()
    assert (
        anonymous.post(comments_url(public_post), {"body": "No"}, format="json").status_code == 403
    )

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    missing = csrf_client.post(
        comments_url(public_post),
        {"body": "Missing token"},
        content_type="application/json",
    )
    token = csrf_client.get("/api/me/").json()["csrf_token"]
    invalid_fields = csrf_client.post(
        comments_url(public_post),
        {"body": "Body", "author": 999, "reply_to_user": 999},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    created = csrf_client.post(
        comments_url(public_post),
        {"body": "  Unicode 👩‍💻\r\nline  "},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )

    assert missing.status_code == 403
    assert invalid_fields.status_code == 400
    assert created.status_code == 201
    assert created.json()["body"] == "Unicode 👩‍💻\nline"


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ("", 400),
        (" \r\n ", 400),
        ("x" * 5000, 201),
        ("x" * 5001, 400),
        ("nul\u0000byte", 400),
        ("bidi\u202etext", 400),
        ("\ufdd0", 400),
        ("\U0010ffff", 400),
    ],
)
def test_body_boundaries(public_post, user, body, status):
    response = login_api(user).post(comments_url(public_post), {"body": body}, format="json")
    assert response.status_code == status


def test_raw_json_surrogate_is_rejected_without_encoding_or_database_error(public_post, user):
    client = login_api(user)
    response = client.generic(
        "POST",
        comments_url(public_post),
        data=b'{"body":"\\ud800"}',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.data["body"]


def test_reply_to_reply_flattens_and_thread_orders_oldest_first(public_post, user, other_user):
    root = create_top_level_comment(post=public_post, author=user, body="Root")
    first = create_reply(target_id=root.pk, author=other_user, body="First")
    response = login_api(user).post(
        reverse("discussions_api:comment-replies", kwargs={"pk": first.pk}),
        {"body": "Second"},
        format="json",
    )
    thread = APIClient().get(reverse("discussions_api:comment-thread", kwargs={"pk": first.pk}))

    assert response.status_code == 201
    assert response.data["thread_root_id"] == root.pk
    assert response.data["reply_to"]["id"] == other_user.pk
    assert thread.data["root"]["id"] == root.pk
    assert [item["body"] for item in thread.data["results"]] == ["First", "Second"]
    assert all(item["kind"] == "reply" for item in thread.data["results"])
    assert thread.data["next"] is None


def test_deleted_and_hidden_bodies_never_leave_public_api(
    public_post, user, other_user, admin_user
):
    deleted = create_top_level_comment(post=public_post, author=user, body="Deleted secret")
    create_reply(target_id=deleted.pk, author=other_user, body="Survives")
    hidden = create_top_level_comment(post=public_post, author=user, body="Hidden secret")
    soft_delete_comment(comment_id=deleted.pk, actor=user)
    set_comment_hidden(comment_id=hidden.pk, moderator=admin_user, hidden=True, reason="private")

    listing = APIClient().get(comments_url(public_post))
    by_id = {item["id"]: item for item in listing.data["results"]}
    thread = APIClient().get(reverse("discussions_api:comment-thread", kwargs={"pk": deleted.pk}))
    serialized = str(listing.data)

    assert by_id[deleted.pk]["status"] == "deleted"
    assert by_id[deleted.pk]["body"] is None
    assert by_id[hidden.pk]["status"] == "hidden"
    assert by_id[hidden.pk]["body"] is None
    assert "Deleted secret" not in serialized
    assert "Hidden secret" not in serialized
    assert "private" not in serialized
    assert thread.data["results"][0]["body"] == "Survives"


def test_owner_edit_delete_permissions_and_noop(public_post, user, other_user, admin_user):
    comment = create_top_level_comment(post=public_post, author=user, body="Original")
    detail = reverse("discussions_api:comment-detail", kwargs={"pk": comment.pk})

    assert login_api(other_user).patch(detail, {"body": "Stolen"}, format="json").status_code == 403
    assert (
        login_api(admin_user).patch(detail, {"body": "Admin edit"}, format="json").status_code
        == 403
    )

    noop = login_api(user).patch(detail, {"body": " Original "}, format="json")
    edited = login_api(user).patch(detail, {"body": "Changed"}, format="json")
    deleted = login_api(user).delete(detail)
    deleted_again = login_api(user).delete(detail)
    rejected_edit = login_api(user).patch(detail, {"body": "After"}, format="json")

    assert noop.data["edited_at"] is None
    assert edited.data["edited_at"] is not None
    assert deleted.status_code == 204
    assert deleted_again.status_code == 204
    assert rejected_edit.status_code == 400


def test_site_author_identity_does_not_grant_cross_owner_or_moderation_permission(
    public_post, user, other_user
):
    from django.core.exceptions import PermissionDenied

    site_author = other_user
    site_author.is_staff = True
    site_author.save(update_fields=("is_staff",))
    owned = create_top_level_comment(post=public_post, author=user, body="Reader-owned")
    authored = create_top_level_comment(post=public_post, author=site_author, body="Author-owned")

    listing = APIClient().get(comments_url(public_post))
    by_id = {item["id"]: item for item in listing.data["results"]}
    assert by_id[authored.pk]["author"]["is_site_author"] is True
    assert (
        login_api(site_author)
        .patch(
            reverse("discussions_api:comment-detail", kwargs={"pk": owned.pk}),
            {"body": "Cross-owner edit"},
            format="json",
        )
        .status_code
        == 403
    )
    with pytest.raises(PermissionDenied):
        set_comment_hidden(comment_id=owned.pk, moderator=site_author, hidden=True)


def test_delete_then_edit_is_deterministically_rejected(public_post, user):
    comment = create_top_level_comment(post=public_post, author=user, body="Original")
    detail = reverse("discussions_api:comment-detail", kwargs={"pk": comment.pk})
    owner = login_api(user)

    assert owner.delete(detail).status_code == 204
    assert owner.patch(detail, {"body": "Too late"}, format="json").status_code == 400
    comment.refresh_from_db()
    assert comment.deleted_at is not None
    assert comment.body == "Original"


def test_banned_and_inactive_users_are_read_only(public_post, user, other_user):
    comment = create_top_level_comment(post=public_post, author=other_user, body="Root")
    user.is_banned = True
    user.save(update_fields=("is_banned",))
    banned = login_api(user).post(comments_url(public_post), {"body": "No"}, format="json")

    user.is_banned = False
    user.is_active = False
    user.save(update_fields=("is_banned", "is_active"))
    inactive = login_api(user).post(comments_url(public_post), {"body": "No"}, format="json")
    reading = APIClient().get(comments_url(public_post))

    assert banned.status_code == 403
    assert inactive.status_code == 403
    assert reading.status_code == 200
    assert reading.data["results"][0]["id"] == comment.pk


def test_hidden_thread_rejects_reply_but_deleted_root_accepts_it(
    public_post, user, other_user, admin_user
):
    root = create_top_level_comment(post=public_post, author=user, body="Root")
    set_comment_hidden(comment_id=root.pk, moderator=admin_user, hidden=True)
    hidden_reply = login_api(other_user).post(
        reverse("discussions_api:comment-replies", kwargs={"pk": root.pk}),
        {"body": "No"},
        format="json",
    )
    set_comment_hidden(comment_id=root.pk, moderator=admin_user, hidden=False)
    soft_delete_comment(comment_id=root.pk, actor=user)
    deleted_reply = login_api(other_user).post(
        reverse("discussions_api:comment-replies", kwargs={"pk": root.pk}),
        {"body": "Allowed"},
        format="json",
    )

    assert hidden_reply.status_code == 403
    assert deleted_reply.status_code == 201


@override_settings(
    COMMENT_CREATE_RATE_LIMIT_COUNT=1,
    COMMENT_CREATE_RATE_LIMIT_WINDOW_SECONDS=60,
)
def test_rate_limit_has_retry_after_and_one_bucket(public_post, user):
    first = login_api(user).post(comments_url(public_post), {"body": "One"}, format="json")
    second = login_api(user).post(comments_url(public_post), {"body": "Two"}, format="json")

    assert first.status_code == 201
    assert second.status_code == 429
    assert int(second["Retry-After"]) >= 1
    assert user.comment_rate_limit_buckets.filter(scope="create").count() == 1


def test_cursor_pagination_is_relative_and_stable_when_new_root_arrives(
    public_post, user, settings
):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK}
    for index in range(22):
        create_top_level_comment(post=public_post, author=user, body=f"Comment {index}")
    client = APIClient()
    first = client.get(comments_url(public_post))
    first_ids = [item["id"] for item in first.data["results"]]
    create_top_level_comment(post=public_post, author=user, body="Inserted later")
    second = client.get(first.data["next"])
    second_ids = [item["id"] for item in second.data["results"]]

    assert first.data["next"].startswith("/api/v1/")
    assert "testserver" not in first.data["next"]
    assert set(first_ids).isdisjoint(second_ids)
    assert len(first_ids) == 20
    assert len(second_ids) == 2
