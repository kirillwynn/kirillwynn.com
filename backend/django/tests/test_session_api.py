import pytest
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model

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
    user = get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
        first_name="Safe",
        last_name="Reader",
        is_staff=True,
    )
    SocialAccount.objects.create(user=user, provider="google", uid="google-1")
    client.force_login(user)

    response = client.get("/api/me/")

    assert response.json()["user"] == {
        "id": user.pk,
        "display_name": "Safe Reader",
        "email": "reader@example.com",
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
    user = get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
        is_banned=True,
    )
    client.force_login(user)

    assert client.get("/api/me/").json()["user"]["can_interact"] is False


def test_inactive_user_session_is_rejected(client):
    user = get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
        is_active=False,
    )
    client.force_login(user)

    payload = client.get("/api/me/").json()

    assert payload["authenticated"] is False
    assert payload["user"] is None


def test_expired_database_session_is_anonymous_and_cannot_restore_authentication(client):
    user = get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
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
    user = get_user_model().objects.create_user(username="reader", email="reader@example.com")
    client.force_login(user)

    get_response = client.get("/api/auth/logout/")
    missing = client.post("/api/auth/logout/")
    token = client.get("/api/me/").json()["csrf_token"]
    invalid = client.post(
        "/api/auth/logout/",
        HTTP_X_CSRFTOKEN="invalid",
    )
    valid = client.post(
        "/api/auth/logout/",
        HTTP_X_CSRFTOKEN=token,
    )
    repeated = client.post("/api/auth/logout/")

    assert get_response.status_code == 405
    assert missing.status_code == 403
    assert invalid.status_code == 403
    assert valid.status_code == 204
    assert "_auth_user_id" not in client.session
    assert repeated.status_code == 204
    assert_private(valid)
