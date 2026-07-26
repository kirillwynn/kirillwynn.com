import pytest
from django.conf import settings
from django.contrib.auth import get_user_model


def test_custom_user_model_is_configured():
    assert settings.AUTH_USER_MODEL == "users.User"


@pytest.mark.parametrize("path", ["/django-admin/", "/cms/"])
def test_admin_routes_require_authentication(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert "login" in response.headers["Location"]


@pytest.mark.django_db
def test_model_backend_password_login_remains_available_for_admin(client):
    user = get_user_model().objects.create_superuser(
        username="owner",
        email="owner@example.com",
        password="safe-test-password",
    )

    assert client.login(username=user.username, password="safe-test-password") is True
    assert client.get("/django-admin/").status_code == 200
    assert client.get("/cms/").status_code == 200


@pytest.mark.django_db
def test_public_allauth_local_login_and_signup_are_disabled(client):
    user_count = get_user_model().objects.count()
    login = client.post(
        "/accounts/login/",
        {"login": "reader@example.com", "password": "not-used"},
    )
    signup = client.post(
        "/accounts/signup/",
        {"email": "reader@example.com", "password1": "not-used"},
    )

    assert login.status_code == 403
    assert signup.status_code == 404
    assert "_auth_user_id" not in client.session
    assert get_user_model().objects.count() == user_count
