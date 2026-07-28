"""Read or issue subscription state for Playwright without adding HTTP URLs."""

from __future__ import annotations

import json
import os
import sys
from urllib.parse import parse_qs, urlsplit

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cross_stack")
django.setup()

from apps.subscriptions.models import EmailOutbox, Subscriber  # noqa: E402
from apps.subscriptions.outbox import claim_outbox_batch, process_outbox_event  # noqa: E402
from apps.subscriptions.providers.memory import MemoryEmailProvider  # noqa: E402
from apps.subscriptions.tokens import issue_credential  # noqa: E402


def main() -> None:
    action, email = sys.argv[1:3]
    subscriber = Subscriber.objects.get(canonical_email=email.casefold())
    if action == "transport-confirm":
        event = EmailOutbox.objects.get(
            subscriber=subscriber,
            message_type=EmailOutbox.MessageType.CONFIRMATION,
        )
        MemoryEmailProvider.reset()
        claimed = claim_outbox_batch(limit=25)
        if event.pk not in claimed:
            raise RuntimeError("confirmation event was not claimed")
        provider = MemoryEmailProvider()
        for event_id in claimed:
            process_outbox_event(event_id, provider=provider)
        prepared_request = next(
            prepared
            for prepared, _ in MemoryEmailProvider.sent
            if json.loads(prepared.body)["to"] == [subscriber.email]
        )
        message = json.loads(prepared_request.body)
        confirmation_url = next(
            line for line in message["text"].splitlines() if "#credential=" in line
        )
        credential = parse_qs(urlsplit(confirmation_url).fragment)["credential"][0]
        print(credential, end="")
    elif action == "unsubscribe":
        print(
            issue_credential(
                subscriber=subscriber,
                purpose="unsubscribe",
                token_version=subscriber.unsubscribe_token_version,
            ),
            end="",
        )
    elif action == "status":
        print(subscriber.status, end="")
    else:
        raise SystemExit(f"unknown action: {action}")


if __name__ == "__main__":
    main()
