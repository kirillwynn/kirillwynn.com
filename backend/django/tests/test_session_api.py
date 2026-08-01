import json

import pytest
from allauth.socialaccount.models import SocialAccount

from tests.identity import create_identity_user

pytestmark = pytest.mark.django_db


def assert_private(response):
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "Cookie" in response.headers["Vary"]


def test_me_anonymous_sets_masked_csrf_token_and_private_headers(client):
    response = client.get("/api/me/")
    payload = response.json()

    assert response.status_code == 200
    assert payload["authenticated"] is False
    assert payload["user"] is None
    assert payload["providers"] == {
        "google": {"available": True, "connected": False},
        "github": {"available": True, "connected": False},
    }
    assert len(payload["csrf_token"]) == 64
    assert len(response.cookies["csrftoken"].value) == 32
    assert payload["csrf_token"] != response.cookies["csrftoken"].value
    assert_private(response)


def test_me_authenticated_returns_minimal_user_and_provider_state(client):
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Safe Reader",
        password="test-password",
        is_staff=True,
    )
    SocialAccount.objects.create(user=user, provider="google", uid="google-1")
    client.force_login(user)

    response = client.get("/api/me/")

    assert response.json()["user"] == {
        "id": user.pk,
        "nickname": "Safe Reader",
        "display_name": "Safe Reader",
        "nickname_suggestion": None,
        "email": "reader@example.com",
        "email_verified": True,
        "profile_complete": True,
        "has_usable_password": True,
        "nickname_change_available_at": None,
        "is_admin": True,
        "is_banned": False,
        "can_interact": True,
    }
    assert response.json()["providers"]["google"]["connected"] is True
    assert response.json()["providers"]["github"]["connected"] is False
    serialized = response.content.decode()
    assert "extra_data" not in serialized
    assert "session" not in serialized
    assert_private(response)


def test_me_disables_interaction_for_banned_user(client):
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Banned Reader",
        is_banned=True,
    )
    client.force_login(user)

    assert client.get("/api/me/").json()["user"]["can_interact"] is False


def test_inactive_user_session_is_rejected(client):
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Inactive Reader",
        is_active=False,
    )
    client.force_login(user)

    payload = client.get("/api/me/").json()

    assert payload["authenticated"] is False
    assert payload["user"] is None


def test_expired_database_session_is_anonymous_and_cannot_restore_authentication(client):
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Expired Reader",
    )
    client.force_login(user)
    session = client.session
    session.set_expiry(-1)
    session.save()

    payload = client.get("/api/me/").json()

    assert payload["authenticated"] is False
    assert payload["user"] is None


def test_authenticated_logout_requires_valid_csrf_and_get_never_logs_out():
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Logout Reader",
    )
    client.force_login(user)

    get_response = client.get("/api/auth/logout/")
    missing = client.post("/api/auth/logout/")
    token = client.get("/api/me/").json()["csrf_token"]
    invalid = client.post(
        "/api/auth/logout/",
        HTTP_X_CSRFTOKEN="invalid",
    )
    unsupported = client.post(
        "/api/auth/logout/",
        data="logout",
        content_type="text/plain",
        HTTP_X_CSRFTOKEN=token,
    )
    nonempty = client.post(
        "/api/auth/logout/",
        data=json.dumps({"unexpected": True}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    valid = client.post(
        "/api/auth/logout/",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    repeated_token = client.get("/api/me/").json()["csrf_token"]
    repeated = client.post(
        "/api/auth/logout/",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=repeated_token,
    )

    assert get_response.status_code == 405
    assert missing.status_code == 403
    assert invalid.status_code == 403
    assert unsupported.status_code == 415
    assert nonempty.status_code == 400
    assert valid.status_code == 204
    assert "_auth_user_id" not in client.session
    assert repeated.status_code == 204
    assert_private(valid)
