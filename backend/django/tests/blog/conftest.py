from io import BytesIO

import pytest
from django.core.files.base import ContentFile
from PIL import Image as PillowImage
from wagtail.images import get_image_model
from wagtail.models import Page

from apps.blog.models import BlogIndexPage, BlogPostPage
from tests.identity import create_identity_user


@pytest.fixture
def blog_author(settings):
    settings.SITE_OWNER_EMAIL = "owner@example.com"
    return create_identity_user(
        username="owner",
        email="owner@example.com",
        nickname="Kirill Wynn",
        password="test-password",
        superuser=True,
        site_author=True,
    )


@pytest.fixture
def blog_index(blog_author):
    root = Page.get_first_root_node()
    index_page = BlogIndexPage(title="Blog", slug="blog", live=False)
    root.add_child(instance=index_page)
    index_page._stage17_author = blog_author
    return index_page


@pytest.fixture
def blog_post(blog_index):
    post = BlogPostPage(
        title="Draft post",
        slug="draft-post",
        excerpt="A concise draft excerpt.",
        body=[("rich_text", "<p>Draft body.</p>")],
        owner=blog_index._stage17_author,
        live=False,
    )
    blog_index.add_child(instance=post)
    return post


@pytest.fixture
def wagtail_image(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    image_buffer = BytesIO()
    PillowImage.new("RGB", (2, 2), "white").save(image_buffer, format="PNG")
    return get_image_model().objects.create(
        title="Test image",
        file=ContentFile(image_buffer.getvalue(), name="test.png"),
    )
