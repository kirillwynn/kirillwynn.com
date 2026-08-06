"""Read non-secret Stage 15 CMS QA state from the isolated cross-stack database."""

from __future__ import annotations

import hashlib
import json
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cross_stack")
django.setup()

from apps.blog.models import BlogPostPage  # noqa: E402
from apps.subscriptions.models import (  # noqa: E402
    EmailDelivery,
    EmailOutbox,
    PostPublicationEmailDecision,
)


def main() -> None:
    slug = sys.argv[1]
    post = BlogPostPage.objects.get(slug=slug)
    try:
        decision = post.publication_email_decision
        decision_state = decision.state
    except PostPublicationEmailDecision.DoesNotExist:
        decision_state = "pending"

    body_json = json.dumps(
        list(post.body.raw_data),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    payload = {
        "body_sha256": hashlib.sha256(body_json.encode()).hexdigest(),
        "block_ids": [item["id"] for item in post.body.raw_data],
        "block_types": [item["type"] for item in post.body.raw_data],
        "decision": decision_state,
        "publication_outbox": EmailOutbox.objects.filter(
            post=post,
            message_type=EmailOutbox.MessageType.PUBLICATION,
        ).count(),
        "deliveries": EmailDelivery.objects.filter(outbox__post=post).count(),
        "live": post.live,
        "go_live_at": post.go_live_at.isoformat() if post.go_live_at else None,
        "expire_at": post.expire_at.isoformat() if post.expire_at else None,
        "revision_count": post.revisions.count(),
        "latest_revision_excerpt": (
            post.get_latest_revision().content.get("excerpt")
            if post.get_latest_revision() is not None
            else None
        ),
        "original_published_at": (
            post.original_published_at.isoformat()
            if post.original_published_at is not None
            else None
        ),
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
