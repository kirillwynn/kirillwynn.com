from urllib.parse import quote

from django.conf import settings
from django.template.loader import render_to_string

from apps.subscriptions.providers.base import EmailMessage
from apps.subscriptions.tokens import issue_credential


def _credential_url(path, credential, *, fragment=True):
    separator = "#credential=" if fragment else "?credential="
    return f"{settings.PUBLIC_SITE_URL}{path}{separator}{quote(credential, safe='')}"


def confirmation_message(delivery):
    subscriber = delivery.subscriber
    credential = issue_credential(
        subscriber=subscriber,
        purpose="confirm",
        token_version=delivery.outbox.credential_version,
    )
    context = {
        "confirmation_url": _credential_url(
            "/subscriptions/confirm/",
            credential,
        )
    }
    return EmailMessage(
        to=subscriber.email,
        subject="Confirm your subscription to Kirill Wynn",
        text=render_to_string("subscriptions/email/confirmation.txt", context),
        html=render_to_string("subscriptions/email/confirmation.html", context),
    )


def publication_message(delivery):
    subscriber = delivery.subscriber
    post = delivery.outbox.post
    credential = issue_credential(
        subscriber=subscriber,
        purpose="unsubscribe",
        token_version=subscriber.unsubscribe_token_version,
    )
    unsubscribe_url = _credential_url(
        "/subscriptions/unsubscribe/",
        credential,
    )
    one_click_url = _credential_url(
        "/api/v1/subscriptions/unsubscribe/one-click/",
        credential,
        fragment=False,
    )
    context = {
        "post_title": post.title,
        "post_excerpt": post.excerpt,
        "post_url": post.resolved_canonical_url,
        "unsubscribe_url": unsubscribe_url,
    }
    return EmailMessage(
        to=subscriber.email,
        subject=f"New post: {post.title}",
        text=render_to_string("subscriptions/email/publication.txt", context),
        html=render_to_string("subscriptions/email/publication.html", context),
        headers={
            "List-Unsubscribe": f"<{one_click_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )


def message_for_delivery(delivery):
    if delivery.outbox.message_type == delivery.outbox.MessageType.CONFIRMATION:
        return confirmation_message(delivery)
    return publication_message(delivery)
