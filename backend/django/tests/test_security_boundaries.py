import pytest
from django.contrib.auth import get_user_model
from django.test import Client

pytestmark = pytest.mark.django_db


def test_csrf_token_is_bound_to_the_issuing_session():
    user = get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
    )
    issuer = Client(enforce_csrf_checks=True)
    issuer.force_login(user)
    foreign_token = issuer.get("/api/me/").json()["csrf_token"]

    other_session = Client(enforce_csrf_checks=True)
    other_session.force_login(user)
    response = other_session.post(
        "/api/auth/logout/",
        HTTP_X_CSRFTOKEN=foreign_token,
    )

    assert response.status_code == 403
    assert other_session.get("/api/me/").json()["authenticated"] is True


def test_cross_origin_and_cross_site_referer_are_rejected_even_with_valid_token():
    user = get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    token = client.get("/api/me/", secure=True).json()["csrf_token"]

    evil_origin = client.post(
        "/api/auth/logout/",
        secure=True,
        HTTP_X_CSRFTOKEN=token,
        HTTP_ORIGIN="https://evil.example",
    )
    evil_referer = client.post(
        "/api/auth/logout/",
        secure=True,
        HTTP_X_CSRFTOKEN=token,
        HTTP_REFERER="https://evil.example/logout",
    )

    assert evil_origin.status_code == 403
    assert evil_referer.status_code == 403
    assert client.get("/api/me/").json()["authenticated"] is True
