import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page

from apps.blog.models import BlogIndexPage, BlogPostPage


@pytest.fixture
def blog_index():
    root = Page.get_first_root_node()
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
