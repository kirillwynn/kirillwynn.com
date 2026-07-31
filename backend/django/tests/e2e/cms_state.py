"""Read non-secret Stage 15 CMS QA state from the isolated cross-stack database."""

from __future__ import annotations

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

    payload = {
        "decision": decision_state,
        "publication_outbox": EmailOutbox.objects.filter(
            post=post,
            message_type=EmailOutbox.MessageType.PUBLICATION,
        ).count(),
        "deliveries": EmailDelivery.objects.filter(outbox__post=post).count(),
        "live": post.live,
        "original_published_at": (
            post.original_published_at.isoformat()
            if post.original_published_at is not None
            else None
        ),
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
