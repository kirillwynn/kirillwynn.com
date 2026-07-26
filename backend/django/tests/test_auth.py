from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin, SocialToken
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, override_settings

from apps.users.adapters import SiteAccountAdapter
from apps.users.return_to import safe_return_to

pytestmark = pytest.mark.django_db

MALICIOUS_RETURN_TO_VALUES = [
    "//evil.example",
    "///evil.example",
    "///posts/foo",
    "////posts/foo",
    "/%2F%2Fposts/foo",
    "/%2f%2fposts/foo",
    "/%252F%252Fposts/foo",
    r"/\evil",
    r"/posts/foo\evil",
    "/posts/foo%5Cevil",
    "/posts/foo\rheader",
    "/posts/foo\nheader",
    "/posts/foo\theader",
    "/posts/foo%0Dheader",
    "/posts/foo%0Aheader",
    "/posts/foo%09header",
    "/posts/foo?value=ok\r\nLocation: //evil.example",
    "/bridge?value=%0D%0ALocation%3A%20%2F%2Fevil.example",
    "/account?value=%09header",
    "http://evil.example/",
    "https://evil.example/",
    "javascript:alert(1)",
    "data:text/html,boom",
    "/posts/foo%",
    "/posts/foo%2",
    "/posts/foo%GG",
    "/api/me/",
    "/accounts/google/login/",
    "/cms/",
    "/django-admin/",
    "/login",
    "/posts/foo/bar",
]


def mocked_social_login(adapter, provider, uid, email, *, verified=True, name="Reader"):
    provider_instance = adapter.get_provider()
    user = get_user_model()(
        username=f"{provider}-{uid}",
        email=email,
        first_name=name,
    )
    return SocialLogin(
        user=user,
        account=SocialAccount(provider=provider, uid=uid, extra_data={"ignored": True}),
        email_addresses=[EmailAddress(email=email, verified=verified, primary=True)],
        provider=provider_instance,
    )


def complete_oauth_callback(
    client,
    provider,
    state,
    uid,
    email,
    *,
    verified=True,
):
    adapter_path = (
        "allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter"
        if provider == "google"
        else "allauth.socialaccount.providers.github.views.GitHubOAuth2Adapter"
    )
    with (
        patch(f"{adapter_path}.get_access_token_data", return_value={"access_token": "temporary"}),
        patch(
            f"{adapter_path}.complete_login",
            autospec=True,
            side_effect=lambda adapter, request, app, token, **kwargs: mocked_social_login(
                adapter, provider, uid, email, verified=verified
            ),
        ),
    ):
        return client.get(
            f"/accounts/{provider}/login/callback/",
            {"code": "mock-code", "state": state},
        )


def oauth_callback(
    client,
    provider,
    uid,
    email,
    *,
    verified=True,
    next_url="/account",
    process="login",
):
    me = client.get("/api/me/").json()
    start = client.post(
        f"/accounts/{provider}/login/",
        {
            "csrfmiddlewaretoken": me["csrf_token"],
            "next": next_url,
            "process": process,
        },
    )
    assert start.status_code == 302
    state = parse_qs(urlsplit(start.headers["Location"]).query)["state"][0]

    return complete_oauth_callback(
        client,
        provider,
        state,
        uid,
        email,
        verified=verified,
    )


@pytest.mark.parametrize("provider", ["google", "github"])
def test_mocked_provider_signup_login_and_repeated_login(provider):
    client = Client(enforce_csrf_checks=True)

    first = oauth_callback(
        client,
        provider,
        f"{provider}-uid",
        f"{provider}@example.com",
        next_url="/posts/привет?from=login",
    )

    assert first.status_code == 302
    assert first.headers["Location"] == ("/posts/%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82?from=login")
    assert get_user_model().objects.count() == 1
    assert SocialAccount.objects.filter(provider=provider).count() == 1
    assert SocialToken.objects.count() == 0
    user_id = client.get("/api/me/").json()["user"]["id"]

    repeated = oauth_callback(
        client,
        provider,
        f"{provider}-uid",
        f"{provider}@example.com",
    )

    assert repeated.status_code == 302
    assert get_user_model().objects.count() == 1
    assert client.get("/api/me/").json()["user"]["id"] == user_id
    assert SocialToken.objects.count() == 0


def test_second_provider_verified_email_matches_and_connects_existing_user():
    client = Client(enforce_csrf_checks=True)
    oauth_callback(client, "google", "google-1", "same@example.com")
    user = get_user_model().objects.get()

    second = oauth_callback(client, "github", "github-1", "same@example.com")

    assert second.status_code == 302
    assert get_user_model().objects.count() == 1
    assert set(user.socialaccount_set.values_list("provider", flat=True)) == {
        "google",
        "github",
    }


def test_explicit_second_provider_connection_for_authenticated_user():
    client = Client(enforce_csrf_checks=True)
    oauth_callback(client, "google", "google-1", "reader@example.com")
    me = client.get("/api/me/").json()
    start = client.post(
        "/accounts/github/login/",
        {
            "csrfmiddlewaretoken": me["csrf_token"],
            "process": "connect",
            "next": "/account",
        },
    )
    state = parse_qs(urlsplit(start.headers["Location"]).query)["state"][0]

    with (
        patch(
            "allauth.socialaccount.providers.github.views.GitHubOAuth2Adapter.get_access_token_data",
            return_value={"access_token": "temporary"},
        ),
        patch(
            "allauth.socialaccount.providers.github.views.GitHubOAuth2Adapter.complete_login",
            autospec=True,
            side_effect=lambda adapter, request, app, token, **kwargs: mocked_social_login(
                adapter, "github", "github-connected", "other-verified@example.com"
            ),
        ),
    ):
        response = client.get(
            "/accounts/github/login/callback/",
            {"code": "mock-code", "state": state},
        )

    assert response.status_code == 302
    assert response.headers["Location"] == "/account"
    assert set(SocialAccount.objects.values_list("provider", flat=True)) == {
        "google",
        "github",
    }
    assert get_user_model().objects.count() == 1


def test_unverified_email_cannot_signup_or_match_existing_user():
    existing = get_user_model().objects.create_user(username="existing", email="victim@example.com")
    client = Client(enforce_csrf_checks=True)

    response = oauth_callback(
        client,
        "github",
        "attacker",
        "victim@example.com",
        verified=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/login?error=verified_email_required"
    assert not SocialAccount.objects.exists()
    assert get_user_model().objects.get() == existing
    assert client.get("/api/me/").json()["authenticated"] is False


def test_identity_cannot_be_reassigned_to_another_authenticated_user():
    owner = get_user_model().objects.create_user(username="owner", email="owner@example.com")
    identity = SocialAccount.objects.create(provider="github", uid="shared", user=owner)
    other = get_user_model().objects.create_user(username="other", email="other@example.com")
    client = Client(enforce_csrf_checks=True)
    client.force_login(other)

    response = oauth_callback(
        client,
        "github",
        identity.uid,
        "owner@example.com",
        process="connect",
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/account?error=identity_in_use"
    assert SocialAccount.objects.get(pk=identity.pk).user == owner
    assert client.get("/api/me/").json()["user"]["id"] == other.pk


def test_connect_cannot_claim_verified_email_of_another_user():
    get_user_model().objects.create_user(
        username="owner",
        email="owner@example.com",
    )
    other = get_user_model().objects.create_user(
        username="other",
        email="other@example.com",
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(other)

    response = oauth_callback(
        client,
        "github",
        "new-identity",
        "owner@example.com",
        process="connect",
    )

    assert response.headers["Location"] == "/account?error=identity_in_use"
    assert not SocialAccount.objects.exists()


def test_connecting_an_already_connected_identity_reports_safe_error():
    user = get_user_model().objects.create_user(
        username="reader",
        email="reader@example.com",
    )
    SocialAccount.objects.create(provider="google", uid="connected", user=user)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    response = oauth_callback(
        client,
        "google",
        "connected",
        "reader@example.com",
        process="connect",
    )

    assert response.headers["Location"] == "/account?error=already_connected"
    assert SocialAccount.objects.count() == 1


def test_banned_social_account_cannot_login():
    user = get_user_model().objects.create_user(
        username="banned", email="banned@example.com", is_banned=True
    )
    SocialAccount.objects.create(provider="google", uid="banned-uid", user=user)

    response = oauth_callback(
        Client(enforce_csrf_checks=True),
        "google",
        "banned-uid",
        "banned@example.com",
    )

    assert response.headers["Location"] == "/login?error=account_unavailable"


def test_tampered_state_and_provider_error_are_generic():
    client = Client()

    tampered = client.get(
        "/accounts/google/login/callback/",
        {"code": "mock-code", "state": "tampered"},
    )
    cancelled = client.get(
        "/accounts/github/login/callback/",
        {"error": "access_denied", "state": "tampered"},
    )

    assert tampered.status_code == 302
    assert tampered.headers["Location"] == "/login?error=oauth"
    assert cancelled.status_code == 302
    assert cancelled.headers["Location"] == "/login?error=oauth"
    assert "mock-code" not in tampered.headers["Location"]


def test_valid_provider_cancellation_and_callback_failure_are_generic():
    client = Client(enforce_csrf_checks=True)
    token = client.get("/api/me/").json()["csrf_token"]
    start = client.post(
        "/accounts/google/login/",
        {"csrfmiddlewaretoken": token, "next": "/bridge"},
    )
    state = parse_qs(urlsplit(start.headers["Location"]).query)["state"][0]
    cancelled = client.get(
        "/accounts/google/login/callback/",
        {"error": "access_denied", "state": state},
    )

    token = client.get("/api/me/").json()["csrf_token"]
    start = client.post(
        "/accounts/google/login/",
        {"csrfmiddlewaretoken": token, "next": "/"},
    )
    state = parse_qs(urlsplit(start.headers["Location"]).query)["state"][0]
    with patch(
        "allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.get_access_token_data",
        side_effect=OAuth2Error("provider detail must not leak"),
    ):
        failure = client.get(
            "/accounts/google/login/callback/",
            {"code": "secret-code", "state": state},
        )

    assert cancelled.headers["Location"] == "/login?error=cancelled"
    assert failure.headers["Location"] == "/login?error=oauth"
    assert "provider detail" not in failure.headers["Location"]
    assert "secret-code" not in failure.headers["Location"]


def test_login_rotates_the_session_key():
    client = Client(enforce_csrf_checks=True)
    token = client.get("/api/me/").json()["csrf_token"]
    start = client.post(
        "/accounts/google/login/",
        {"csrfmiddlewaretoken": token, "next": "/"},
    )
    state = parse_qs(urlsplit(start.headers["Location"]).query)["state"][0]
    before = client.cookies["sessionid"].value
    with (
        patch(
            "allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.get_access_token_data",
            return_value={"access_token": "temporary"},
        ),
        patch(
            "allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.complete_login",
            autospec=True,
            side_effect=lambda adapter, request, app, token, **kwargs: mocked_social_login(
                adapter,
                "google",
                "rotating-user",
                "rotating@example.com",
            ),
        ),
    ):
        client.get(
            "/accounts/google/login/callback/",
            {"code": "mock-code", "state": state},
        )

    assert client.cookies["sessionid"].value != before


def test_social_login_requires_post_and_csrf():
    client = Client(enforce_csrf_checks=True)

    get_response = client.get("/accounts/google/login/")
    post_without_csrf = client.post("/accounts/google/login/")
    token = client.get("/api/me/").json()["csrf_token"]
    post_with_csrf = client.post(
        "/accounts/google/login/",
        {"csrfmiddlewaretoken": token, "next": "/"},
    )

    assert get_response.status_code == 200
    assert "Google" in get_response.content.decode()
    assert post_without_csrf.status_code == 403
    assert post_with_csrf.status_code == 302


@override_settings(
    SOCIALACCOUNT_PROVIDERS={
        "google": {"APPS": []},
        "github": {"APPS": []},
    }
)
def test_unavailable_provider_returns_safe_generic_state():
    response = Client().get("/accounts/google/login/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login?error=provider_unavailable"


@pytest.mark.parametrize(
    "value",
    MALICIOUS_RETURN_TO_VALUES,
)
def test_return_to_rejects_unsafe_or_service_routes(value):
    request = RequestFactory().get("/")
    adapter = SiteAccountAdapter(request)

    assert safe_return_to(value) == "/"
    assert adapter.is_safe_url(value) is False


@pytest.mark.parametrize(
    "value",
    [
        "/",
        "/bridge",
        "/account",
        "/posts/hello-world",
        "/posts/привет-мир",
        "/posts/hello?reply=42",
        "/bridge?from=post%20menu",
    ],
)
def test_return_to_accepts_only_allowlisted_frontend_routes(value):
    request = RequestFactory().get("/")
    adapter = SiteAccountAdapter(request)

    assert adapter.is_safe_url(value) is True


@pytest.mark.parametrize("provider", ["google", "github"])
@pytest.mark.parametrize("next_url", MALICIOUS_RETURN_TO_VALUES)
def test_malicious_next_is_not_stashed_or_returned_after_oauth_callback(provider, next_url):
    client = Client(enforce_csrf_checks=True)
    token = client.get("/api/me/").json()["csrf_token"]

    response = client.post(
        f"/accounts/{provider}/login/",
        {
            "csrfmiddlewaretoken": token,
            "next": next_url,
        },
    )
    assert response.status_code == 302
    state = parse_qs(urlsplit(response.headers["Location"]).query)["state"][0]

    assert client.session["socialaccount_states"][state][0].get("next") is None

    callback = complete_oauth_callback(
        client,
        provider,
        state,
        f"{provider}-redirect-regression",
        f"{provider}-redirect@example.com",
    )

    assert callback.status_code == 302
    assert callback.headers["Location"] == "/"
    parsed_location = urlsplit(callback.headers["Location"])
    assert not parsed_location.scheme
    assert not parsed_location.netloc
