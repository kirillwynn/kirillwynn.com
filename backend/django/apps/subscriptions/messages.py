from urllib.parse import quote

from django.template.loader import render_to_string

from apps.subscriptions.providers.base import EmailMessage
from apps.subscriptions.tokens import issue_credential

MESSAGE_SCHEMA_VERSION = 1


def _credential_url(site_url, path, credential, *, fragment=True):
    separator = "#credential=" if fragment else "?credential="
    return f"{site_url}{path}{separator}{quote(credential, safe='')}"


def _confirmation_message_v1(delivery):
    subscriber = delivery.subscriber
    event = delivery.outbox
    credential = issue_credential(
        subscriber=subscriber,
        purpose="confirm",
        token_version=delivery.snapshot_credential_version,
        issued_at=delivery.credential_issued_at,
    )
    context = {
        "confirmation_url": _credential_url(
            event.snapshot_site_url,
            "/subscriptions/confirm/",
            credential,
        )
    }
    return EmailMessage(
        from_email=event.snapshot_from_email,
        to=delivery.snapshot_recipient_email,
        subject=event.snapshot_subject,
        text=render_to_string("subscriptions/email/confirmation.txt", context),
        html=render_to_string("subscriptions/email/confirmation.html", context),
    )


def _publication_message_v1(delivery):
    subscriber = delivery.subscriber
    event = delivery.outbox
    credential = issue_credential(
        subscriber=subscriber,
        purpose="unsubscribe",
        token_version=delivery.snapshot_credential_version,
        issued_at=delivery.credential_issued_at,
    )
    unsubscribe_url = _credential_url(
        event.snapshot_site_url,
        "/subscriptions/unsubscribe/",
        credential,
    )
    one_click_url = _credential_url(
        event.snapshot_site_url,
        "/api/v1/subscriptions/unsubscribe/one-click/",
        credential,
        fragment=False,
    )
    context = {
        "post_title": event.snapshot_post_title,
        "post_excerpt": event.snapshot_post_excerpt,
        "post_url": event.snapshot_post_url,
        "unsubscribe_url": unsubscribe_url,
    }
    return EmailMessage(
        from_email=event.snapshot_from_email,
        to=delivery.snapshot_recipient_email,
        subject=event.snapshot_subject,
        text=render_to_string("subscriptions/email/publication.txt", context),
        html=render_to_string("subscriptions/email/publication.html", context),
        headers={
            "List-Unsubscribe": f"<{one_click_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )


def message_for_delivery(delivery):
    if delivery.outbox.message_schema_version != MESSAGE_SCHEMA_VERSION:
        raise ValueError("Unsupported immutable email message schema")
    if delivery.outbox.message_type == delivery.outbox.MessageType.CONFIRMATION:
        return _confirmation_message_v1(delivery)
    return _publication_message_v1(delivery)
