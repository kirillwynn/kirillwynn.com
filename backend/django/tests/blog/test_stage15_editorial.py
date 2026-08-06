import json
from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page

from apps.blog.models import BlogPostPage, PreviewSnapshot, RevalidationEvent
from apps.blog.services.visibility import public_blog_posts
from apps.blog.wagtail_hooks import new_post_add_url
from apps.subscriptions.models import EmailOutbox, PostPublicationEmailDecision

pytestmark = pytest.mark.django_db


def publish(page):
    page.save_revision().publish()
    return BlogPostPage.objects.get(pk=page.pk)


def add_post(blog_index, *, slug, original_published_at=None):
    post = BlogPostPage(
        title=slug.replace("-", " ").title(),
        slug=slug,
        excerpt=f"Excerpt for {slug}.",
        body=[("rich_text", f"<p>Body for {slug}.</p>")],
        original_published_at=original_published_at,
        owner=blog_index._stage17_author,
        live=False,
    )
    blog_index.add_child(instance=post)
    return post


def make_superuser():
    return get_user_model().objects.create_superuser(
        username="stage15-owner",
        email="stage15-owner@example.com",
        password="safe-test-password",
    )


def test_original_publication_date_is_nullable_and_rejects_naive_or_future_values(blog_post):
    blog_post.original_published_at = None
    blog_post.full_clean()

    blog_post.original_published_at = datetime(2020, 1, 2, 3, 4)
    with pytest.raises(ValidationError) as naive_error:
        blog_post.clean()
    assert "time zone" in naive_error.value.message_dict["original_published_at"][0]

    blog_post.original_published_at = timezone.now() + timedelta(minutes=1)
    with pytest.raises(ValidationError) as future_error:
        blog_post.full_clean()
    assert future_error.value.message_dict["original_published_at"] == [
        "Original publication date cannot be in the future."
    ]


def test_original_date_on_published_post_cannot_follow_actual_site_publication(blog_post):
    published = publish(blog_post)
    actual_first = published.first_published_at - timedelta(days=10)
    Page.objects.filter(pk=published.pk).update(first_published_at=actual_first)
    published.refresh_from_db()
    published.original_published_at = actual_first + timedelta(days=5)

    with pytest.raises(ValidationError) as error:
        published.full_clean()

    assert "first publication on this site" in error.value.message_dict["original_published_at"][0]


def test_editor_form_reports_invalid_original_date_at_the_field(blog_post):
    form_class = BlogPostPage.get_edit_handler().get_form_class()
    form = form_class(
        data={
            "title": blog_post.title,
            "slug": blog_post.slug,
            "excerpt": blog_post.excerpt,
            "body-count": "0",
            "original_published_at": "not-a-date",
            "notify_subscribers_on_first_publication": "on",
        },
        instance=blog_post,
    )

    assert form.is_valid() is False
    assert "original_published_at" in form.errors
    assert "valid date/time" in form.errors["original_published_at"][0]


def test_original_date_and_notification_intent_are_revision_content(blog_post):
    archived_at = timezone.now() - timedelta(days=365)
    blog_post.original_published_at = archived_at
    blog_post.notify_subscribers_on_first_publication = False
    archive_revision = blog_post.save_revision()

    blog_post.original_published_at = None
    blog_post.notify_subscribers_on_first_publication = True
    blog_post.save_revision()
    restored = archive_revision.as_object()

    assert restored.original_published_at == archived_at
    assert restored.notify_subscribers_on_first_publication is False
    assert BlogPostPage.objects.get(pk=blog_post.pk).first_published_at is None
    assert not PostPublicationEmailDecision.objects.filter(post_id=blog_post.pk).exists()
    assert not EmailOutbox.objects.exists()


def test_headless_and_backend_preview_use_immutable_original_display_date(blog_post):
    archived_at = datetime(2017, 6, 4, 12, 30, tzinfo=UTC)
    blog_post.original_published_at = archived_at
    revision = blog_post.save_revision()
    draft = revision.as_object()

    headless = draft.make_preview_request(preview_mode="headless")
    credential = headless.cookies["kw_preview_credential"].value
    resolved = APIClient().post(
        reverse("blog_api:preview-resolve"),
        {"credential": credential},
        format="json",
    )
    backend = draft.make_preview_request(preview_mode="backend")

    assert resolved.status_code == 200
    assert resolved.data["published_at"] is None
    assert resolved.data["original_published_at"] == "2017-06-04T12:30:00Z"
    assert resolved.data["display_published_at"] == "2017-06-04T12:30:00Z"
    assert 'datetime="2017-06-04T12:30:00+00:00"' in backend.rendered_content
    snapshot = PreviewSnapshot.objects.get()
    assert json.loads(snapshot.content_json)["original_published_at"] == ("2017-06-04T12:30:00Z")
    assert BlogPostPage.objects.get(pk=blog_post.pk).live is False


def test_api_keeps_actual_timestamps_and_adds_original_and_display_dates(blog_post):
    archived_at = datetime(2018, 2, 3, 4, 5, tzinfo=UTC)
    blog_post.original_published_at = archived_at
    published = publish(blog_post)

    response = APIClient().get(reverse("blog_api:post-detail", kwargs={"slug": published.slug}))

    assert response.status_code == 200
    assert response.data["original_published_at"] == "2018-02-03T04:05:00Z"
    assert response.data["display_published_at"] == "2018-02-03T04:05:00Z"
    assert response.data["published_at"] != response.data["display_published_at"]
    assert response.data["published_at"].endswith("Z")
    assert response.data["updated_at"].endswith("Z")


def test_api_display_date_falls_back_to_actual_site_publication(blog_post):
    published = publish(blog_post)

    response = APIClient().get(reverse("blog_api:post-detail", kwargs={"slug": published.slug}))

    assert response.status_code == 200
    assert response.data["original_published_at"] is None
    assert response.data["display_published_at"] == response.data["published_at"]


def test_feed_orders_by_display_date_then_descending_pk_with_stable_pagination(blog_index):
    tie = datetime(2020, 5, 1, 12, tzinfo=UTC)
    oldest = publish(
        add_post(
            blog_index,
            slug="oldest-archive",
            original_published_at=datetime(2010, 1, 1, tzinfo=UTC),
        )
    )
    tie_lower_pk = publish(add_post(blog_index, slug="tie-lower", original_published_at=tie))
    tie_higher_pk = publish(add_post(blog_index, slug="tie-higher", original_published_at=tie))
    newest = publish(
        add_post(
            blog_index,
            slug="newest-archive",
            original_published_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )

    response = APIClient().get(
        reverse("blog_api:post-list"),
        {"page_size": 2},
    )
    second = APIClient().get(
        reverse("blog_api:post-list"),
        {"page_size": 2, "page": 2},
    )
    slugs = [
        *(item["slug"] for item in response.data["results"]),
        *(item["slug"] for item in second.data["results"]),
    ]

    assert slugs == [
        newest.slug,
        tie_higher_pk.slug,
        tie_lower_pk.slug,
        oldest.slug,
    ]
    assert len(slugs) == len(set(slugs))
    assert "COALESCE" in str(public_blog_posts().query).upper()


def test_draft_original_date_does_not_reorder_feed_until_republished(blog_index):
    older = publish(
        add_post(
            blog_index,
            slug="older",
            original_published_at=datetime(2019, 1, 1, tzinfo=UTC),
        )
    )
    newer = publish(
        add_post(
            blog_index,
            slug="newer",
            original_published_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
    )
    list_url = reverse("blog_api:post-list")
    assert [item["slug"] for item in APIClient().get(list_url).data["results"]] == [
        newer.slug,
        older.slug,
    ]

    older.original_published_at = datetime(2021, 1, 1, tzinfo=UTC)
    draft = older.save_revision()
    assert [item["slug"] for item in APIClient().get(list_url).data["results"]] == [
        newer.slug,
        older.slug,
    ]

    draft.publish()
    assert [item["slug"] for item in APIClient().get(list_url).data["results"]] == [
        older.slug,
        newer.slug,
    ]
    assert RevalidationEvent.objects.filter(page_id=older.pk).count() == 2


def test_dashboard_and_menu_new_post_shortcut_resolve_dynamic_parent(client, blog_index):
    client.force_login(make_superuser())

    dashboard = client.get(reverse("wagtailadmin_home"))
    shortcut = client.get(reverse("blog_new_post"))

    assert dashboard.status_code == 200
    assert dashboard.content.count(b"New post") >= 2
    assert b"Start with the post" in dashboard.content
    assert b"blog/css/editorial-admin.css" in dashboard.content
    assert b"blog/js/editorial-admin.js" not in dashboard.content
    assert shortcut.status_code == 302
    assert shortcut.headers["Location"] == new_post_add_url(blog_index)
    assert str(blog_index.pk) in shortcut.headers["Location"]


def test_new_post_shortcut_hides_and_denies_without_page_add_permission(client, blog_index):
    user = get_user_model().objects.create_user(
        username="editor-without-page-permission",
        email="limited@example.com",
        password="safe-test-password",
        is_staff=True,
    )
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtailadmin",
            codename="access_admin",
        )
    )
    client.force_login(user)

    dashboard = client.get(reverse("wagtailadmin_home"))
    shortcut = client.get(reverse("blog_new_post"))

    assert dashboard.status_code == 200
    assert b"You do not have permission to add a post" in dashboard.content
    assert shortcut.status_code == 302
    assert shortcut.headers["Location"] == reverse("wagtailadmin_home")


def test_new_post_shortcut_handles_missing_blog_index_without_guessing(client):
    client.force_login(make_superuser())

    dashboard = client.get(reverse("wagtailadmin_home"))
    shortcut = client.get(reverse("blog_new_post"), follow=True)

    assert dashboard.status_code == 200
    assert b"Blog index is missing" in dashboard.content
    assert shortcut.redirect_chain == [(reverse("wagtailadmin_home"), 302)]
    assert b"Restore the BlogIndexPage" in shortcut.content


def test_add_editor_exposes_writing_first_tabs_labels_and_all_block_descriptions(
    client,
    blog_index,
):
    client.force_login(make_superuser())

    response = client.get(new_post_add_url(blog_index))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Write" in content
    assert "Publish" in content
    assert "SEO &amp; sharing" in content
    assert 'class="w-form-width" data-editorial-surface="writing"' in content
    assert 'data-editorial-surface="publishing"' in content
    assert 'data-editorial-surface="sharing"' in content
    assert 'data-editorial-field="title"' in content
    assert 'data-editorial-field="body"' in content
    assert "blog/js/editorial-admin.js" in content
    assert "Original publication date" in content
    assert "Notify subscribers on first publication" in content
    assert "Newsletter decision" in content
    assert "internal classification, search relevance, and metadata" in content
    assert "Feed filters" not in content
    for group in ("Text", "Media", "Lists", "Code / Data", "Structure"):
        assert group in content
    for block_type in (
        "rich_text",
        "heading",
        "image",
        "gallery",
        "quote",
        "bulleted_list",
        "numbered_list",
        "checklist",
        "inline_code",
        "code_block",
        "table",
        "horizontal_divider",
        "link",
    ):
        assert f"data-editorial-block&quot;: &quot;{block_type}" in content
    for description in (
        "Paragraphs with bold, italic, and links.",
        "One image with contextual alt text.",
        "A quotation with optional attribution.",
        "A visual break between sections.",
    ):
        assert description in content
