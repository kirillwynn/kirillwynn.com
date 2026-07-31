import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from taggit.models import Tag
from wagtail.models import Page

from apps.blog.models import BlogIndexPage, BlogPostPage, BlogPostTag

pytestmark = pytest.mark.django_db


def test_page_hierarchy_and_blog_index_singleton(blog_index):
    root = Page.get_first_root_node()

    assert BlogIndexPage.can_exist_under(root)
    assert not BlogIndexPage.can_exist_under(blog_index)
    assert not BlogIndexPage.can_create_at(root)
    assert BlogPostPage.can_create_at(blog_index)
    assert not BlogPostPage.can_create_at(root)
    assert BlogIndexPage.allowed_subpage_models() == [BlogPostPage]
    assert BlogPostPage.allowed_subpage_models() == []
    assert BlogPostPage.allowed_parent_page_models() == [BlogIndexPage]


def test_blog_index_can_initially_only_be_created_at_root():
    root = Page.get_first_root_node()

    assert BlogIndexPage.can_create_at(root)


def test_post_requires_excerpt_and_body(blog_post):
    blog_post.excerpt = ""
    blog_post.body = []

    with pytest.raises(ValidationError) as error:
        blog_post.full_clean()

    assert {"excerpt", "body"} <= error.value.error_dict.keys()


def test_post_rejects_non_http_canonical_url(blog_post):
    blog_post.canonical_url = "ftp://example.com/post"

    with pytest.raises(ValidationError) as error:
        blog_post.full_clean()

    assert "canonical_url" in error.value.error_dict


def test_tags_are_case_insensitive_slugged_and_saved_once(blog_post):
    blog_post.tags.add("Django", "django", "Wagtail", "Разработка")
    blog_post.save()

    tags = {tag.name: tag.slug for tag in blog_post.tags.all()}
    assert tags == {
        "Django": "django",
        "Wagtail": "wagtail",
        "Разработка": "разработка",
    }
    assert BlogPostTag.objects.filter(content_object=blog_post).count() == 3


def test_duplicate_post_tag_relation_is_database_constrained(blog_post):
    tag = Tag.objects.create(name="Python")
    BlogPostTag.objects.create(content_object=blog_post, tag=tag)

    with pytest.raises(IntegrityError), transaction.atomic():
        BlogPostTag.objects.create(content_object=blog_post, tag=tag)


def test_seo_and_open_graph_fallbacks(blog_post):
    assert blog_post.resolved_open_graph_title == "Draft post"
    assert blog_post.resolved_open_graph_description == "A concise draft excerpt."

    blog_post.seo_title = "SEO title"
    blog_post.search_description = "Search description"
    assert blog_post.resolved_open_graph_title == "SEO title"
    assert blog_post.resolved_open_graph_description == "Search description"

    blog_post.open_graph_title = "Social title"
    blog_post.open_graph_description = "Social description"
    blog_post.canonical_url = "https://example.com/canonical"
    assert blog_post.resolved_open_graph_title == "Social title"
    assert blog_post.resolved_open_graph_description == "Social description"
    assert blog_post.resolved_canonical_url == "https://example.com/canonical"


def test_fallback_canonical_url_uses_public_origin_with_unicode_slug(blog_post):
    blog_post.slug = "привет-мир"

    assert blog_post.resolved_canonical_url == (
        "http://localhost:3000/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82-%D0%BC%D0%B8%D1%80"
    )


def test_post_uses_wagtail_publication_fields_without_custom_status():
    field_names = {field.name for field in BlogPostPage._meta.get_fields()}

    assert {
        "live",
        "first_published_at",
        "last_published_at",
        "go_live_at",
        "expire_at",
    } <= field_names
    assert "status" not in field_names


def test_authoring_panels_include_content_tags_and_metadata():
    edit_handler = BlogPostPage.get_edit_handler()

    def fields(panel):
        result = {panel.field_name} if hasattr(panel, "field_name") else set()
        for child in getattr(panel, "children", []):
            result.update(fields(child))
        return result

    assert [panel.heading for panel in edit_handler.children] == [
        "Write",
        "Publish",
        "SEO & sharing",
    ]
    panel_fields = fields(edit_handler)
    assert {
        "title",
        "excerpt",
        "body",
        "tags",
        "original_published_at",
        "notify_subscribers_on_first_publication",
        "newsletter_status",
        "canonical_url",
        "open_graph_image",
        "open_graph_title",
        "open_graph_description",
    } <= panel_fields


def test_wagtail_editor_form_exposes_publication_seo_and_content_fields():
    form_fields = set(BlogPostPage.get_edit_handler().get_form_class().base_fields)

    assert {
        "title",
        "slug",
        "excerpt",
        "body",
        "tags",
        "original_published_at",
        "notify_subscribers_on_first_publication",
        "seo_title",
        "search_description",
        "canonical_url",
        "open_graph_image",
        "open_graph_title",
        "open_graph_description",
        "go_live_at",
        "expire_at",
    } <= form_fields
