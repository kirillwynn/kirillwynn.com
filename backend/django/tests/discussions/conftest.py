import hashlib

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.models import Locale, Page, Site

from apps.blog.models import BlogIndexPage, BlogPostPage
from apps.discussions.models import ReactionCatalogItem


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


@pytest.fixture
def reaction_catalog_items():
    specs = (
        ("pepeclap", "Pepe clap", "Clapping", "animated"),
        ("pepehmm", "Pepe hmm", "Thinking", "static"),
        ("pepelove", "Pepe love", "Sending love", "static"),
    )
    items = []
    for ordering, (catalog_id, name, label, kind) in enumerate(specs, start=1):
        source_sha = hashlib.sha256(f"source:{catalog_id}".encode()).hexdigest()
        normalized_sha = hashlib.sha256(f"normalized:{catalog_id}".encode()).hexdigest()
        poster_sha = (
            hashlib.sha256(f"poster:{catalog_id}".encode()).hexdigest()
            if kind == "animated"
            else ""
        )
        directory = f"reactions/{catalog_id}/{normalized_sha}"
        items.append(
            ReactionCatalogItem.objects.create(
                catalog_id=catalog_id,
                display_name=name,
                accessibility_label=label,
                kind=kind,
                ordering=ordering * 10,
                enabled=True,
                selectable=True,
                quick_order=ordering,
                source_sha256=source_sha,
                normalized_sha256=normalized_sha,
                poster_sha256=poster_sha,
                immutable_asset_version=f"sha256-{normalized_sha}",
                intrinsic_width=64,
                intrinsic_height=64,
                frame_count=3 if kind == "animated" else 1,
                duration_ms=120 if kind == "animated" else 0,
                minimum_frame_delay_ms=40 if kind == "animated" else 0,
                asset_storage_key=(
                    f"{directory}/animation.gif"
                    if kind == "animated"
                    else f"{directory}/asset.webp"
                ),
                poster_storage_key=(f"{directory}/poster.webp" if kind == "animated" else ""),
                provenance_source="Synthetic test fixture",
                provenance_author="Test suite",
                license="Synthetic",
                rights_basis="Generated for tests",
                approval_status="staging-only/unverified",
                manifest_sha256=hashlib.sha256(b"test manifest").hexdigest(),
                imported_at=timezone.now(),
            )
        )
    return tuple(items)


@pytest.fixture
def reaction_catalog_item(reaction_catalog_items):
    return reaction_catalog_items[0]
