import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.models import Locale, Page, Site

from apps.blog.models import BlogIndexPage, BlogPostPage


@pytest.fixture
def blog_index():
    root = Page.get_first_root_node()
    if root is None:
        locale, _ = Locale.objects.get_or_create(
            language_code=get_supported_content_language_variant(settings.LANGUAGE_CODE)
        )
        root = Page.add_root(instance=Page(title="Root", slug="root", locale=locale))
        Site.objects.create(
            hostname="localhost",
            root_page=root,
            is_default_site=True,
        )
    index = BlogIndexPage(title="Blog", slug="blog", live=False)
    root.add_child(instance=index)
    return index


@pytest.fixture
def public_post(blog_index):
    post = BlogPostPage(
        title="Public comments",
        slug="привет-мир",
        excerpt="A public post.",
        body=[("rich_text", "<p>Public body.</p>")],
        live=False,
    )
    blog_index.add_child(instance=post)
    post.save_revision().publish()
    return BlogPostPage.objects.get(pk=post.pk)


@pytest.fixture
def user():
    return get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
        password="test-password",
        first_name="Safe",
        last_name="Reader",
    )


@pytest.fixture
def other_user():
    return get_user_model().objects.create_user(
        username="other",
        email="other@example.com",
        password="test-password",
    )


@pytest.fixture
def admin_user():
    return get_user_model().objects.create_superuser(
        username="owner",
        email="owner@example.com",
        password="test-password",
    )
