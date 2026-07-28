"""Seed the isolated SQLite database used by cross-stack Playwright."""

from __future__ import annotations

import json
import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cross_stack")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from wagtail.models import Page, Site  # noqa: E402

from apps.blog.models import BlogIndexPage, BlogPostPage  # noqa: E402
from apps.discussions.models import (  # noqa: E402
    Comment,
    PostReaction,
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
    PostReaction.objects.create(post=post, user=author, emoji="🔥")

    settings = ReactionSettings.for_site(site)
    settings.quick_reaction_one = "🔥"
    settings.quick_reaction_two = "🎉"
    settings.quick_reaction_three = "👍"
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
