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
def blog_post(blog_index):
    post = BlogPostPage(
        title="A new <safe> post",
        slug="new-post",
        excerpt="An excerpt with <script> text.",
        body=[("rich_text", "<p>Body that must not enter email.</p>")],
        live=False,
    )
    blog_index.add_child(instance=post)
    return post


@pytest.fixture
def admin_user():
    return get_user_model().objects.create_superuser(
        username="owner",
        email="owner@example.com",
        password="test-password",
    )
