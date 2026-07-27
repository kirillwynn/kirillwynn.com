from datetime import timedelta

import pytest
from django.core import signing
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.subscriptions.models import (
    EmailDelivery,
    EmailOutbox,
    Subscriber,
    SubscriptionRateLimitBucket,
)
from apps.subscriptions.outbox import confirmation_outbox_snapshot
from apps.subscriptions.rate_limits import client_ip
from apps.subscriptions.services import (
    confirm_subscription,
    request_subscription,
    suppress_subscriber,
)
from apps.subscriptions.tokens import issue_credential

pytestmark = pytest.mark.django_db


def csrf_client():
    client = APIClient(enforce_csrf_checks=True)
    response = client.get(reverse("core:current-user"))
    return client, response.data["csrf_token"]


def post_with_csrf(client, url, data, token, **extra):
    return client.post(
        url,
        data,
        format="json",
        HTTP_X_CSRFTOKEN=token,
        **extra,
    )


def confirmation_credential(subscriber):
    return issue_credential(
        subscriber=subscriber,
        purpose="confirm",
        token_version=subscriber.confirmation_token_version,
    )


def unsubscribe_credential(subscriber):
    return issue_credential(
        subscriber=subscriber,
        purpose="unsubscribe",
        token_version=subscriber.unsubscribe_token_version,
    )


def test_anonymous_subscribe_requires_csrf_and_returns_generic_202():
    url = reverse("subscriptions_api:subscribe")
    blocked = APIClient(enforce_csrf_checks=True).post(
        url,
        {"email": "reader@example.com"},
        format="json",
    )
    client, token = csrf_client()
    accepted = post_with_csrf(
        client,
        url,
        {"email": " Reader@Example.com "},
        token,
    )

    assert blocked.status_code == 403
    assert accepted.status_code == 202
    assert accepted.data == {
        "detail": "If the address can be subscribed, a confirmation email will be sent."
    }
    subscriber = Subscriber.objects.get()
    assert subscriber.canonical_email == "reader@example.com"
    assert subscriber.status == Subscriber.Status.PENDING
    assert EmailOutbox.objects.get().message_type == EmailOutbox.MessageType.CONFIRMATION


def test_subscription_api_accepts_json_only():
    client, token = csrf_client()
    response = client.post(
        reverse("subscriptions_api:subscribe"),
        {"email": "reader@example.com"},
        HTTP_X_CSRFTOKEN=token,
    )

    assert response.status_code == 415


@override_settings(SUBSCRIPTION_RATE_LIMIT_COUNT=100)
def test_subscribe_response_resists_active_suppressed_and_unknown_enumeration():
    active = Subscriber.objects.create(
        email="active@example.com",
        status=Subscriber.Status.ACTIVE,
        confirmed_at=timezone.now(),
    )
    suppressed = Subscriber.objects.create(email="suppressed@example.com")
    suppress_subscriber(suppressed.pk, reason="complaint")
    client, token = csrf_client()
    url = reverse("subscriptions_api:subscribe")

    responses = [
        post_with_csrf(client, url, {"email": address}, token)
        for address in (
            "new@example.com",
            active.email,
            suppressed.email,
        )
    ]

    assert {response.status_code for response in responses} == {202}
    assert len({response.content for response in responses}) == 1
    assert active.outbox_events.count() == 0
    assert suppressed.outbox_events.count() == 0


def test_confirm_is_explicit_post_idempotent_and_purpose_bound():
    subscriber = request_subscription("reader@example.com")
    credential = confirmation_credential(subscriber)
    client, token = csrf_client()
    url = reverse("subscriptions_api:confirm")

    assert client.get(url).status_code == 405
    first = post_with_csrf(client, url, {"credential": credential}, token)
    repeated = post_with_csrf(client, url, {"credential": credential}, token)
    wrong_purpose = post_with_csrf(
        client,
        url,
        {"credential": unsubscribe_credential(subscriber)},
        token,
    )
    tampered = post_with_csrf(
        client,
        url,
        {"credential": f"{credential}x"},
        token,
    )

    assert first.data == {"status": "confirmed"}
    assert repeated.data == {"status": "already_confirmed"}
    assert wrong_purpose.status_code == tampered.status_code == 400
    assert wrong_purpose.data == tampered.data
    subscriber.refresh_from_db()
    assert subscriber.status == Subscriber.Status.ACTIVE
    assert subscriber.confirmed_at is not None


def test_expired_and_superseded_confirmation_credentials_are_identical(monkeypatch):
    now = timezone.now()
    monkeypatch.setattr(signing.time, "time", lambda: now.timestamp())
    subscriber = request_subscription("reader@example.com", at=now)
    expired = confirmation_credential(subscriber)
    request_subscription(
        "reader@example.com",
        at=now + timedelta(seconds=901),
    )
    subscriber.refresh_from_db()
    superseded = expired
    current = confirmation_credential(subscriber)
    monkeypatch.setattr(
        signing.time,
        "time",
        lambda: (now + timedelta(hours=49)).timestamp(),
    )
    client, token = csrf_client()
    url = reverse("subscriptions_api:confirm")

    old_response = post_with_csrf(client, url, {"credential": superseded}, token)
    expired_response = post_with_csrf(client, url, {"credential": current}, token)

    assert old_response.status_code == expired_response.status_code == 400
    assert old_response.data == expired_response.data


def test_unsubscribe_get_never_mutates_and_post_is_idempotent():
    subscriber = request_subscription("reader@example.com")
    confirm_subscription(confirmation_credential(subscriber))
    subscriber.refresh_from_db()
    credential = unsubscribe_credential(subscriber)
    client, token = csrf_client()
    url = reverse("subscriptions_api:unsubscribe")

    assert client.get(url).status_code == 405
    subscriber.refresh_from_db()
    assert subscriber.status == Subscriber.Status.ACTIVE
    first = post_with_csrf(client, url, {"credential": credential}, token)
    repeated = post_with_csrf(client, url, {"credential": credential}, token)

    assert first.data == {"status": "unsubscribed"}
    assert repeated.data == {"status": "already_unsubscribed"}
    subscriber.refresh_from_db()
    assert subscriber.status == Subscriber.Status.UNSUBSCRIBED


def test_resubscribe_requires_new_opt_in_and_suppression_cannot_be_bypassed():
    now = timezone.now()
    subscriber = request_subscription("reader@example.com", at=now)
    confirm_subscription(confirmation_credential(subscriber), at=now)
    subscriber.refresh_from_db()
    old_unsubscribe = unsubscribe_credential(subscriber)
    client, token = csrf_client()
    post_with_csrf(
        client,
        reverse("subscriptions_api:unsubscribe"),
        {"credential": old_unsubscribe},
        token,
    )
    request_subscription(
        "reader@example.com",
        at=now + timedelta(minutes=20),
    )
    subscriber.refresh_from_db()
    assert subscriber.status == Subscriber.Status.PENDING
    confirm_subscription(confirmation_credential(subscriber), at=now + timedelta(minutes=21))
    subscriber.refresh_from_db()
    assert subscriber.status == Subscriber.Status.ACTIVE

    stale = post_with_csrf(
        client,
        reverse("subscriptions_api:unsubscribe"),
        {"credential": old_unsubscribe},
        token,
    )
    assert stale.status_code == 400

    suppress_subscriber(subscriber.pk, reason="hard_bounce")
    request_subscription(
        "reader@example.com",
        at=now + timedelta(hours=1),
    )
    subscriber.refresh_from_db()
    assert subscriber.status == Subscriber.Status.SUPPRESSED
    assert subscriber.suppression_reason == "hard_bounce"


@override_settings(
    SUBSCRIPTION_RATE_LIMIT_COUNT=1,
    SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS=60,
)
def test_anonymous_rate_limit_is_database_backed_hashed_and_has_retry_after():
    client, token = csrf_client()
    url = reverse("subscriptions_api:subscribe")
    first = post_with_csrf(client, url, {"email": "one@example.com"}, token)
    second = post_with_csrf(client, url, {"email": "two@example.com"}, token)

    assert first.status_code == 202
    assert second.status_code == 429
    assert second["Retry-After"] == "60"
    buckets = SubscriptionRateLimitBucket.objects.all()
    assert buckets.count() == 2
    assert all(len(bucket.key_hash) == 64 for bucket in buckets)
    assert not any("127.0.0.1" in bucket.key_hash for bucket in buckets)
    assert not any("one@example.com" in bucket.key_hash for bucket in buckets)


@override_settings(ALLAUTH_TRUSTED_PROXY_COUNT=1)
def test_subscription_ip_uses_the_existing_rightmost_trusted_proxy_contract():
    request = RequestFactory().get(
        "/",
        HTTP_X_FORWARDED_FOR="198.51.100.9, 192.0.2.20",
        REMOTE_ADDR="192.0.2.30",
    )

    assert client_ip(request) == "192.0.2.20"


def test_one_click_requires_exact_post_body_and_skips_unsent_delivery():
    subscriber = request_subscription("reader@example.com")
    confirm_subscription(confirmation_credential(subscriber))
    subscriber.refresh_from_db()
    now = timezone.now()
    outbox = EmailOutbox.objects.create(
        message_type=EmailOutbox.MessageType.CONFIRMATION,
        subscriber=subscriber,
        credential_version=subscriber.confirmation_token_version,
        available_at=now,
        idempotency_key="temporary-confirmation-shape",
        **confirmation_outbox_snapshot(),
    )
    delivery = EmailDelivery.objects.create(
        outbox=outbox,
        subscriber=subscriber,
        available_at=now,
        snapshot_recipient_email=subscriber.email,
        snapshot_credential_version=subscriber.confirmation_token_version,
        credential_issued_at=now,
        provider_contract_id="test.fixture",
        provider_serializer_version=1,
        provider_idempotency_namespace="test/api",
        provider_payload_hash="0" * 64,
    )
    credential = unsubscribe_credential(subscriber)
    url = f"{reverse('subscriptions_api:unsubscribe-one-click')}?credential={credential}"
    client = APIClient()

    assert client.get(url).status_code == 405
    assert (
        client.post(url, "wrong=body", content_type="application/x-www-form-urlencoded").status_code
        == 400
    )
    response = client.post(
        url,
        "List-Unsubscribe=One-Click",
        content_type="application/x-www-form-urlencoded",
    )

    assert response.status_code == 200
    subscriber.refresh_from_db()
    delivery.refresh_from_db()
    assert subscriber.status == Subscriber.Status.UNSUBSCRIBED
    assert delivery.status == EmailDelivery.Status.SKIPPED
