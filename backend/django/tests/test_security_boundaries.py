import pytest
from django.test import Client
from django.urls import get_resolver

from tests.identity import create_identity_user

pytestmark = pytest.mark.django_db


def test_test_helpers_are_absent_from_the_application_urlconf(settings):
    assert settings.ROOT_URLCONF == "config.urls"
    routes = [str(pattern.pattern) for pattern in get_resolver().url_patterns]

    assert all("__" not in route and "e2e" not in route for route in routes)


def test_csrf_token_is_bound_to_its_csrf_cookie_secret_not_login_session(settings):
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="CSRF Reader",
    )
    issuer = Client(enforce_csrf_checks=True)
    issuer.force_login(user)
    foreign_token = issuer.get("/api/me/").json()["csrf_token"]

    other_session = Client(enforce_csrf_checks=True)
    other_session.force_login(user)
    rejected = other_session.post(
        "/api/auth/logout/",
        data="{}",
        content_type="application/json",
        HTTP_X_CSRFTOKEN=foreign_token,
    )
    assert rejected.status_code == 403
    assert other_session.get("/api/me/").json()["authenticated"] is True

    other_session.cookies[settings.CSRF_COOKIE_NAME] = issuer.cookies[
        settings.CSRF_COOKIE_NAME
    ].value
    accepted = other_session.post(
        "/api/auth/logout/",
        data="{}",
        content_type="application/json",
        HTTP_X_CSRFTOKEN=foreign_token,
    )

    assert accepted.status_code == 204


def test_cross_origin_and_cross_site_referer_are_rejected_even_with_valid_token():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Origin Reader",
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
