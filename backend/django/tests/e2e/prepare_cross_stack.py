"""Seed the isolated SQLite database used by cross-stack Playwright."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cross_stack")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402
from wagtail.models import Page, Site  # noqa: E402

from apps.blog.models import BlogIndexPage, BlogPostPage  # noqa: E402
from apps.discussions.models import (  # noqa: E402
    Comment,
    PostReaction,
    ReactionCatalogItem,
    ReactionSettings,
)


def main() -> None:
    root = Page.get_first_root_node()
    site = Site.objects.get(is_default_site=True)
    site.hostname = "localhost"
    site.port = 3200
    site.site_name = "Cross-stack test"
    site.save()

    index = BlogIndexPage(title="Test blog", slug="blog", live=False)
    root.add_child(instance=index)
    index.save_revision().publish()

    post = BlogPostPage(
        title="Cross-stack systems",
        slug="cross-stack-systems",
        excerpt="Real Django, sessions, CSRF, API views, rewrites, and persistence.",
        body=[("rich_text", "<p>Public cross-stack content.</p>")],
        live=False,
    )
    index.add_child(instance=post)
    post.tags.add("Django", "Security")
    post.save_revision().publish()
    post = BlogPostPage.objects.get(pk=post.pk)

    author = get_user_model().objects.create_user(
        username="site-author",
        email="author@example.test",
        first_name="Site",
        last_name="Author",
        is_staff=True,
    )
    Comment.objects.create(
        post=post,
        author=author,
        body="Seeded root for the real Django thread.",
    )
    catalog = []
    for ordering, (catalog_id, name, label, kind) in enumerate(
        (
            ("pepeclap", "Pepe clap", "Clapping", "animated"),
            ("pepehmm", "Pepe hmm", "Thinking", "static"),
            ("pepelove", "Pepe love", "Sending love", "static"),
        ),
        start=1,
    ):
        source_sha = hashlib.sha256(f"source:{catalog_id}".encode()).hexdigest()
        normalized_sha = hashlib.sha256(f"normalized:{catalog_id}".encode()).hexdigest()
        poster_sha = (
            hashlib.sha256(f"poster:{catalog_id}".encode()).hexdigest()
            if kind == "animated"
            else ""
        )
        directory = f"reactions/{catalog_id}/{normalized_sha}"
        catalog.append(
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
                provenance_source="Synthetic cross-stack fixture",
                provenance_author="Test suite",
                license="Synthetic",
                rights_basis="Generated for tests",
                approval_status="staging-only/unverified",
                manifest_sha256=hashlib.sha256(b"cross-stack manifest").hexdigest(),
                imported_at=timezone.now(),
            )
        )
    PostReaction.objects.create(
        post=post,
        user=author,
        catalog_item=catalog[0],
    )

    settings = ReactionSettings.for_site(site)
    settings.quick_reaction_item_one = catalog[0]
    settings.quick_reaction_item_two = catalog[1]
    settings.quick_reaction_item_three = catalog[2]
    settings.save()

    draft = BlogPostPage.objects.get(pk=post.pk)
    draft.title = "Draft: cross-stack systems"
    preview_response = (
        draft.save_revision().as_object().make_preview_request(preview_mode="headless")
    )
    state = {
        "preview_credential": preview_response.cookies["kw_preview_credential"].value,
        "post_slug": post.slug,
    }
    Path(
        os.environ.get(
            "CROSS_STACK_STATE_FILE",
            "/tmp/kirillwynn-cross-stack-state.json",
        )
    ).write_text(json.dumps(state), encoding="utf-8")


if __name__ == "__main__":
    main()
