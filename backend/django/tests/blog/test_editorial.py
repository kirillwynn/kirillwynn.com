from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from wagtail.models import Revision

from apps.blog.models import BlogPostPage

pytestmark = pytest.mark.django_db


def test_draft_revision_renders_in_backend_preview(blog_post):
    revision = blog_post.save_revision()
    draft = revision.as_object()

    response = draft.make_preview_request(preview_mode="backend")
    rendered = response.rendered_content

    assert response.status_code == 200
    assert "Backend preview: Draft post" in rendered
    assert "<h1>Draft post</h1>" in rendered
    assert "Draft body." in rendered
    assert BlogPostPage.objects.get(pk=blog_post.pk).live is False


def test_draft_image_preview_uses_wagtail_rendition_and_contextual_alt(blog_post, wagtail_image):
    blog_post.body = [
        {
            "type": "image",
            "value": {
                "image": wagtail_image.pk,
                "decorative": False,
                "alt_text": "Preview-specific alt text",
            },
        }
    ]
    revision = blog_post.save_revision()

    rendered = revision.as_object().make_preview_request(preview_mode="backend").rendered_content

    assert 'alt="Preview-specific alt text"' in rendered
    assert wagtail_image.renditions.filter(filter_spec="max-1200x1200").exists()


def test_tags_are_preserved_in_draft_revision(blog_post):
    blog_post.tags.add("Django", "Wagtail")

    revision = blog_post.save_revision()
    draft = revision.as_object()

    assert set(draft.tags.names()) == {"Django", "Wagtail"}


def test_revision_can_be_published_immediately(blog_post):
    revision = blog_post.save_revision()

    revision.publish()
    published = BlogPostPage.objects.get(pk=blog_post.pk)

    assert published.live is True
    assert published.first_published_at is not None
    assert published.last_published_at is not None
    assert published.has_unpublished_changes is False


def test_previous_revision_content_can_be_restored_as_a_new_revision(blog_post):
    original_revision = blog_post.save_revision()
    blog_post.excerpt = "Updated excerpt."
    updated_revision = blog_post.save_revision()

    restored_revision = original_revision.as_object().save_revision()
    restored = BlogPostPage.objects.get(pk=blog_post.pk).get_latest_revision_as_object()

    assert restored.excerpt == "A concise draft excerpt."
    assert restored_revision.pk not in {original_revision.pk, updated_revision.pk}
    assert Revision.page_revisions.filter(object_id=blog_post.pk).count() == 3


def test_future_scheduled_post_is_not_published_early(blog_post):
    go_live_at = timezone.now() + timedelta(days=1)
    blog_post.go_live_at = go_live_at

    revision = blog_post.save_revision()
    revision.publish()
    call_command("publish_scheduled_pages", verbosity=0)

    scheduled = BlogPostPage.objects.get(pk=blog_post.pk)
    assert scheduled.live is False
    assert scheduled.go_live_at == go_live_at
    assert Revision.page_revisions.filter(
        object_id=blog_post.pk,
        approved_go_live_at=go_live_at,
    ).exists()


def test_due_scheduled_post_is_published(blog_post):
    go_live_at = timezone.now() - timedelta(minutes=1)
    blog_post.go_live_at = go_live_at
    blog_post.save_revision(approved_go_live_at=go_live_at)

    call_command("publish_scheduled_pages", verbosity=0)

    published = BlogPostPage.objects.get(pk=blog_post.pk)
    assert published.live is True
    assert published.first_published_at is not None


def test_scheduled_unpublish_waits_until_expiry_and_then_unpublishes(blog_post):
    blog_post.expire_at = timezone.now() + timedelta(days=1)
    blog_post.save_revision().publish()

    call_command("publish_scheduled_pages", verbosity=0)
    assert BlogPostPage.objects.get(pk=blog_post.pk).live is True

    BlogPostPage.objects.filter(pk=blog_post.pk).update(
        expire_at=timezone.now() - timedelta(minutes=1)
    )
    call_command("publish_scheduled_pages", verbosity=0)

    expired = BlogPostPage.objects.get(pk=blog_post.pk)
    assert expired.live is False
    assert expired.expired is True
