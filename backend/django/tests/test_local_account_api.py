import json
from datetime import timedelta

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import resolve
from django.utils import timezone

from apps.subscriptions.models import Subscriber
from apps.users.auth_email import queue_auth_email
from apps.users.credentials import issue_credential, new_credential
from apps.users.models import (
    AuthCredential,
    AuthEmailOutbox,
    AuthRateLimitBucket,
    NicknameHistory,
)
from apps.users.rate_limits import consume_auth_rate_limit
from tests.identity import create_identity_user

pytestmark = pytest.mark.django_db

PASSWORD = "Stage17!passphrase934"
NEW_PASSWORD = "Stage17!replacement582"


def csrf(client):
    return client.get("/api/me/").json()["csrf_token"]


def json_mutation(client, path, payload, *, token=None, method="post", **extra):
    request = getattr(client, method)
    return request(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token or csrf(client),
        **extra,
    )


def assert_private(response):
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "Cookie" in response.headers["Vary"]


def test_local_signup_creates_one_canonical_unverified_identity_and_durable_email():
    client = Client(enforce_csrf_checks=True)

    response = json_mutation(
        client,
        "/api/auth/signup/",
        {
            "email": "  Reader@Example.com ",
            "nickname": "  Åke   Reader  ",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "detail": "If the address can be registered, a verification email will be sent."
    }
    user = get_user_model().objects.get()
    assert user.email == user.email_normalized == "reader@example.com"
    assert user.username.startswith("usr_")
    assert "reader" not in user.username
    assert user.nickname == "Åke Reader"
    assert user.nickname_normalized == "åke reader"
    assert user.nickname_confirmed is True
    assert user.check_password(PASSWORD)
    address = EmailAddress.objects.get(user=user)
    assert (address.email, address.primary, address.verified) == (
        "reader@example.com",
        True,
        False,
    )
    credential = AuthCredential.objects.get(user=user)
    raw = issue_credential(credential)
    assert credential.credential_digest not in raw
    assert raw not in repr(list(AuthCredential.objects.values()))
    assert AuthEmailOutbox.objects.filter(user=user).count() == 1
    assert Subscriber.objects.count() == 0
    assert client.get("/api/me/").json()["authenticated"] is False
    assert_private(response)


def test_signup_is_csrf_json_shape_and_body_bound_with_stable_surrogate_400(settings):
    client = Client(enforce_csrf_checks=True)
    payload = {
        "email": "reader@example.com",
        "nickname": "Reader",
        "password": PASSWORD,
        "password_confirmation": PASSWORD,
    }

    missing_csrf = client.post(
        "/api/auth/signup/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    wrong_media = client.post(
        "/api/auth/signup/",
        data=payload,
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    unexpected = json_mutation(
        client,
        "/api/auth/signup/",
        {**payload, "username": "public-username"},
    )
    wrong_type = json_mutation(
        client,
        "/api/auth/signup/",
        {**payload, "email": ["reader@example.com"]},
    )
    surrogate = client.post(
        "/api/auth/signup/",
        data=(
            b'{"email":"reader@example.com","nickname":"\\ud800x",'
            b'"password":"Stage17!passphrase934",'
            b'"password_confirmation":"Stage17!passphrase934"}'
        ),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    password_surrogate = client.post(
        "/api/auth/signup/",
        data=(
            b'{"email":"reader@example.com","nickname":"Reader",'
            b'"password":"Stage17!\\ud800passphrase",'
            b'"password_confirmation":"Stage17!\\ud800passphrase"}'
        ),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    duplicate_key = client.post(
        "/api/auth/signup/",
        data=(
            b'{"email":"first@example.com","email":"second@example.com",'
            b'"nickname":"Reader","password":"Stage17!passphrase934",'
            b'"password_confirmation":"Stage17!passphrase934"}'
        ),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    deeply_nested = client.post(
        "/api/auth/signup/",
        data=b'{"email":' + (b"[" * 1_100) + b"0" + (b"]" * 1_100) + b"}",
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    settings.AUTH_API_MAX_BODY_BYTES = 64
    oversized = client.post(
        "/api/auth/signup/",
        data=b'{"padding":"' + (b"x" * 100) + b'"}',
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )

    assert missing_csrf.status_code == 403
    assert wrong_media.status_code == 415
    assert wrong_media.json() == {"detail": "Content-Type must be application/json."}
    assert unexpected.status_code == 400
    assert wrong_type.status_code == 400
    assert wrong_type.json() == {"email": "This field must be a string."}
    assert surrogate.status_code == 400
    assert surrogate.headers["Content-Type"].startswith("application/json")
    assert b"Traceback" not in surrogate.content and b"<html" not in surrogate.content
    assert password_surrogate.status_code == 400
    assert password_surrogate.json() == {"detail": "Malformed JSON."}
    assert duplicate_key.status_code == 400
    assert deeply_nested.status_code == 400
    assert duplicate_key.json() == {"detail": "Malformed JSON."}
    assert b"Traceback" not in deeply_nested.content and b"<html" not in deeply_nested.content
    assert oversized.status_code == 400
    assert not get_user_model().objects.exists()


def test_signup_is_case_insensitive_enumeration_resistant_and_nickname_claim_is_permanent():
    client = Client(enforce_csrf_checks=True)
    first = json_mutation(
        client,
        "/api/auth/signup/",
        {
            "email": "Reader@example.com",
            "nickname": "Unique Reader",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
    )
    duplicate = json_mutation(
        client,
        "/api/auth/signup/",
        {
            "email": "reader@EXAMPLE.COM",
            "nickname": "Different Reader",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
    )
    nickname_collision = json_mutation(
        client,
        "/api/auth/signup/",
        {
            "email": "other@example.com",
            "nickname": "unique reader",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
    )
    duplicate_with_collision = json_mutation(
        client,
        "/api/auth/signup/",
        {
            "email": "READER@example.com",
            "nickname": "UNIQUE READER",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
    )

    assert first.status_code == duplicate.status_code == 202
    assert first.json() == duplicate.json()
    assert nickname_collision.status_code == duplicate_with_collision.status_code == 409
    assert nickname_collision.json() == duplicate_with_collision.json()
    assert get_user_model().objects.count() == 1
    assert NicknameHistory.objects.count() == 1


def test_local_login_rotates_session_and_uses_only_email_with_safe_return_to():
    user = create_identity_user(
        username="legacy-internal",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
    )
    client = Client(enforce_csrf_checks=True)
    session = client.session
    session["pre_auth"] = "present"
    session.save()
    before = session.session_key

    response = json_mutation(
        client,
        "/api/auth/login/",
        {
            "email": "READER@EXAMPLE.COM",
            "password": PASSWORD,
            "next": "//evil.example",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "authenticated"
    assert response.json()["next"] == "/"
    assert response.json()["requires_profile_completion"] is False
    assert client.session.session_key != before
    assert client.get("/api/me/").json()["user"]["id"] == user.pk
    assert_private(response)


def test_incomplete_local_login_requires_profile_completion_without_auth_return_to():
    create_identity_user(
        username="legacy-incomplete",
        email="incomplete@example.com",
        nickname="Incomplete Reader",
        nickname_confirmed=False,
        password=PASSWORD,
    )
    client = Client(enforce_csrf_checks=True)

    response = json_mutation(
        client,
        "/api/auth/login/",
        {
            "email": "incomplete@example.com",
            "password": PASSWORD,
            "next": "/posts/welcome",
        },
    )

    assert response.status_code == 200
    assert response.json()["next"] == "/posts/welcome"
    assert response.json()["requires_profile_completion"] is True


def test_wrong_unknown_inactive_and_banned_login_share_generic_failure():
    create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
    )
    create_identity_user(
        username="inactive",
        email="inactive@example.com",
        nickname="Inactive Reader",
        password=PASSWORD,
        is_active=False,
    )
    create_identity_user(
        username="banned",
        email="banned@example.com",
        nickname="Banned Reader",
        password=PASSWORD,
        is_banned=True,
    )

    responses = []
    for email, password in (
        ("reader@example.com", "wrong-password"),
        ("unknown@example.com", "wrong-password"),
        ("inactive@example.com", PASSWORD),
        ("banned@example.com", PASSWORD),
    ):
        current = Client(enforce_csrf_checks=True)
        responses.append(
            json_mutation(
                current,
                "/api/auth/login/",
                {"email": email, "password": password},
            )
        )

    assert {(response.status_code, response.content) for response in responses} == {
        (400, b'{"detail":"The email or password is invalid."}')
    }


def test_email_verification_is_one_time_tamper_resistant_and_preserves_session():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
        verified=False,
    )
    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.VERIFY_EMAIL)
    raw = issue_credential(event.credential)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    before = client.session.session_key

    tampered = json_mutation(
        client,
        "/api/auth/verify-email/",
        {"credential": f"{raw[:-1]}{'A' if raw[-1] != 'A' else 'B'}"},
    )
    verified = json_mutation(
        client,
        "/api/auth/verify-email/",
        {"credential": raw},
    )
    used = json_mutation(
        client,
        "/api/auth/verify-email/",
        {"credential": raw},
    )

    assert (tampered.status_code, tampered.json()["status"]) == (400, "invalid")
    assert (verified.status_code, verified.json()["status"]) == (200, "verified")
    assert (used.status_code, used.json()["status"]) == (409, "used")
    assert EmailAddress.objects.get(user=user, primary=True).verified is True
    assert client.session.session_key == before
    assert client.get("/api/me/").json()["user"]["can_interact"] is True


def test_email_verification_reuses_a_canonical_equivalent_allauth_address():
    user = create_identity_user(
        username="reader",
        email="kirill@example.com",
        nickname="Reader",
        password=PASSWORD,
        verified=False,
    )
    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.VERIFY_EMAIL)
    EmailAddress.objects.filter(user=user).update(email="Kirill@example.com")

    response = json_mutation(
        Client(enforce_csrf_checks=True),
        "/api/auth/verify-email/",
        {"credential": issue_credential(event.credential)},
    )

    assert response.status_code == 200
    assert list(
        EmailAddress.objects.filter(user=user).values_list("email", "primary", "verified")
    ) == [("kirill@example.com", True, True)]


def test_auth_credentials_are_cryptographically_purpose_bound():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
    )
    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.PASSWORD_RESET)
    raw = issue_credential(event.credential)
    client = Client(enforce_csrf_checks=True)

    response = json_mutation(
        client,
        "/api/auth/verify-email/",
        {"credential": raw},
    )

    assert response.status_code == 400
    assert response.json()["status"] == "invalid"
    event.credential.refresh_from_db()
    assert event.credential.used_at is None


def test_expired_and_unavailable_verification_credentials_fail_closed():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    record, expired_raw = new_credential(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
        ttl=timedelta(seconds=-1),
    )
    record.save()
    client = Client(enforce_csrf_checks=True)
    expired = json_mutation(
        client,
        "/api/auth/verify-email/",
        {"credential": expired_raw},
    )

    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.VERIFY_EMAIL)
    raw = issue_credential(event.credential)
    user.is_banned = True
    user.save(update_fields=("is_banned",))
    unavailable = json_mutation(
        client,
        "/api/auth/verify-email/",
        {"credential": raw},
    )

    assert (expired.status_code, expired.json()["status"]) == (410, "expired")
    assert (unavailable.status_code, unavailable.json()["status"]) == (
        403,
        "unavailable",
    )


def test_direct_password_and_availability_saves_revoke_credentials_permanently():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
        verified=False,
    )
    password_event = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
    )
    initial_version = user.auth_state_version

    user.set_password(NEW_PASSWORD)
    user.save(update_fields=("password",))

    user.refresh_from_db()
    password_event.credential.refresh_from_db()
    assert user.auth_state_version == initial_version + 1
    assert password_event.credential.revoked_at is not None

    availability_event = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
    )
    raw = issue_credential(availability_event.credential)
    user.is_banned = True
    user.save(update_fields=("is_banned",))
    user.is_banned = False
    user.save(update_fields=("is_banned",))

    unavailable_after_reversal = json_mutation(
        Client(enforce_csrf_checks=True),
        "/api/auth/verify-email/",
        {"credential": raw},
    )
    availability_event.credential.refresh_from_db()
    assert availability_event.credential.revoked_at is not None
    assert unavailable_after_reversal.status_code == 400
    assert unavailable_after_reversal.json()["status"] == "invalid"

    email_event = queue_auth_email(
        user=user,
        purpose=AuthCredential.Purpose.VERIFY_EMAIL,
    )
    version_before_email_mutation = user.auth_state_version
    user.email = "changed-outside-supported-flow@example.com"
    user.save(update_fields=("email",))

    user.refresh_from_db()
    email_event.credential.refresh_from_db()
    assert user.auth_state_version == version_before_email_mutation + 1
    assert email_event.credential.revoked_at is not None


def test_resend_and_reset_requests_are_enumeration_resistant():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
        verified=False,
    )
    client = Client(enforce_csrf_checks=True)
    known = json_mutation(
        client,
        "/api/auth/verify-email/resend/",
        {"email": "reader@example.com"},
    )
    unknown = json_mutation(
        Client(enforce_csrf_checks=True),
        "/api/auth/verify-email/resend/",
        {"email": "unknown@example.com"},
    )

    assert (known.status_code, known.content) == (unknown.status_code, unknown.content)
    assert AuthCredential.objects.filter(user=user).count() == 1

    EmailAddress.objects.filter(user=user).update(verified=True)
    known_reset = json_mutation(
        client,
        "/api/auth/password/reset/",
        {"email": "READER@example.com"},
    )
    unknown_reset = json_mutation(
        Client(enforce_csrf_checks=True),
        "/api/auth/password/reset/",
        {"email": "missing@example.com"},
    )
    assert (known_reset.status_code, known_reset.content) == (
        unknown_reset.status_code,
        unknown_reset.content,
    )
    assert (
        AuthCredential.objects.filter(
            user=user, purpose=AuthCredential.Purpose.PASSWORD_RESET
        ).count()
        == 1
    )


def test_password_reset_invalidates_sessions_preserves_oauth_and_is_one_time():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
    )
    SocialAccount.objects.create(user=user, provider="google", uid="google-reader")
    first_session = Client()
    second_session = Client()
    first_session.force_login(user)
    second_session.force_login(user)
    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.PASSWORD_RESET)
    raw = issue_credential(event.credential)
    reset_client = Client(enforce_csrf_checks=True)

    response = json_mutation(
        reset_client,
        "/api/auth/password/reset/confirm/",
        {
            "credential": raw,
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        },
    )
    repeated = json_mutation(
        reset_client,
        "/api/auth/password/reset/confirm/",
        {
            "credential": raw,
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
    )

    user.refresh_from_db()
    assert response.json() == {"status": "password_reset"}
    assert (repeated.status_code, repeated.json()["status"]) == (409, "used")
    assert user.check_password(NEW_PASSWORD)
    assert SocialAccount.objects.filter(user=user, provider="google").exists()
    assert first_session.get("/api/me/").json()["authenticated"] is False
    assert second_session.get("/api/me/").json()["authenticated"] is False


def test_password_reset_credential_requires_the_current_verified_primary_email():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
    )
    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.PASSWORD_RESET)
    raw = issue_credential(event.credential)
    EmailAddress.objects.filter(user=user, primary=True).update(verified=False)

    response = json_mutation(
        Client(enforce_csrf_checks=True),
        "/api/auth/password/reset/confirm/",
        {
            "credential": raw,
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        },
    )

    assert (response.status_code, response.json()["status"]) == (400, "invalid")
    event.credential.refresh_from_db()
    user.refresh_from_db()
    assert event.credential.used_at is None
    assert user.check_password(PASSWORD)


def test_password_reset_accepts_the_canonical_verified_primary_identity():
    user = create_identity_user(
        username="reader",
        email="kirill@example.com",
        nickname="Reader",
        password=PASSWORD,
    )
    EmailAddress.objects.filter(user=user).update(email="Kirill@example.com")
    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.PASSWORD_RESET)

    response = json_mutation(
        Client(enforce_csrf_checks=True),
        "/api/auth/password/reset/confirm/",
        {
            "credential": issue_credential(event.credential),
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        },
    )

    user.refresh_from_db()
    assert response.status_code == 200
    assert user.check_password(NEW_PASSWORD)


def test_oauth_only_password_set_and_password_change_keep_only_current_session():
    user = create_identity_user(
        username="oauth",
        email="oauth@example.com",
        nickname="OAuth Reader",
        password=None,
    )
    user.set_unusable_password()
    user.save(update_fields=("password",))
    SocialAccount.objects.create(user=user, provider="github", uid="github-oauth")
    current = Client(enforce_csrf_checks=True)
    current.force_login(user)
    other_before_set = Client()
    other_before_set.force_login(user)
    set_response = json_mutation(
        current,
        "/api/auth/password/set/",
        {"password": PASSWORD, "password_confirmation": PASSWORD},
    )

    assert set_response.status_code == 200
    assert current.get("/api/me/").json()["authenticated"] is True
    assert other_before_set.get("/api/me/").json()["authenticated"] is False
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    assert SocialAccount.objects.filter(user=user).count() == 1

    other = Client()
    other.force_login(user)
    change_response = json_mutation(
        current,
        "/api/auth/password/change/",
        {
            "current_password": PASSWORD,
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        },
    )
    assert change_response.status_code == 200
    assert current.get("/api/me/").json()["authenticated"] is True
    assert other.get("/api/me/").json()["authenticated"] is False


def test_password_set_requires_a_verified_oauth_identity():
    user = create_identity_user(
        username="not-oauth",
        email="not-oauth@example.com",
        nickname="Not OAuth",
        password=None,
    )
    user.set_unusable_password()
    user.save(update_fields=("password",))
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    without_provider = json_mutation(
        client,
        "/api/auth/password/set/",
        {"password": PASSWORD, "password_confirmation": PASSWORD},
    )
    unsupported = SocialAccount.objects.create(
        user=user,
        provider="unsupported-provider",
        uid="unsupported-provider-identity",
    )
    without_supported_provider = json_mutation(
        client,
        "/api/auth/password/set/",
        {"password": PASSWORD, "password_confirmation": PASSWORD},
    )
    unsupported.delete()
    SocialAccount.objects.create(user=user, provider="github", uid="not-oauth-yet")
    EmailAddress.objects.filter(user=user, primary=True).update(verified=False)
    without_verification = json_mutation(
        client,
        "/api/auth/password/set/",
        {"password": PASSWORD, "password_confirmation": PASSWORD},
    )

    user.refresh_from_db()
    assert without_provider.status_code == 403
    assert without_supported_provider.status_code == 403
    assert without_verification.status_code == 403
    assert not user.has_usable_password()


def test_profile_completion_then_rename_enforces_cooldown_and_history_claims():
    user = create_identity_user(
        username="oauth",
        email="oauth@example.com",
        nickname="user-provisional",
    )
    user.nickname_confirmed = False
    user.save(update_fields=("nickname_confirmed",))
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    completed = json_mutation(
        client,
        "/api/auth/profile/",
        {"nickname": "Public Reader"},
        method="patch",
    )
    renamed = json_mutation(
        client,
        "/api/auth/profile/",
        {"nickname": "Final Reader"},
        method="patch",
    )
    cooldown = json_mutation(
        client,
        "/api/auth/profile/",
        {"nickname": "Too Soon"},
        method="patch",
    )

    assert completed.status_code == renamed.status_code == 200
    assert completed.json()["nickname_change_available_at"] is None
    assert renamed.json()["nickname_change_available_at"] is not None
    assert cooldown.status_code == 400
    user.refresh_from_db()
    assert user.nickname == "Final Reader"
    assert user.nickname_changed_at <= timezone.now()
    assert set(user.nickname_history.values_list("nickname_normalized", flat=True)) == {
        "user-provisional",
        "public reader",
        "final reader",
    }

    other = create_identity_user(
        username="other",
        email="other@example.com",
        nickname="Other Reader",
    )
    other_client = Client(enforce_csrf_checks=True)
    other_client.force_login(other)
    unavailable = json_mutation(
        other_client,
        "/api/auth/profile/",
        {"nickname": "Public Reader"},
        method="patch",
    )
    assert unavailable.status_code in {400, 409}


def test_profile_completion_can_confirm_the_existing_backfilled_nickname():
    user = create_identity_user(
        username="legacy-reader",
        email="legacy-reader@example.com",
        nickname="Legacy Reader",
    )
    user.nickname_confirmed = False
    user.save(update_fields=("nickname_confirmed",))
    original_claims = user.nickname_history.count()
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    response = json_mutation(
        client,
        "/api/auth/profile/",
        {"nickname": "Legacy Reader"},
        method="patch",
    )

    assert response.status_code == 200
    assert response.json()["nickname_change_available_at"] is None
    user.refresh_from_db()
    assert user.nickname_confirmed is True
    assert user.nickname_changed_at is None
    assert user.nickname_history.count() == original_claims


@override_settings(
    AUTH_RATE_LIMITS={
        "login_ip": (1, 60),
        "login_email": (100, 60),
    }
)
def test_auth_rate_limit_is_database_backed_and_returns_retry_after():
    first_client = Client(enforce_csrf_checks=True)
    first = json_mutation(
        first_client,
        "/api/auth/login/",
        {"email": "missing@example.com", "password": "wrong"},
    )
    second_client = Client(enforce_csrf_checks=True)
    limited = json_mutation(
        second_client,
        "/api/auth/login/",
        {"email": "different@example.com", "password": "wrong"},
    )

    assert first.status_code == 400
    assert limited.status_code == 429
    assert 1 <= int(limited.headers["Retry-After"]) <= 60
    assert_private(limited)


@override_settings(AUTH_RATE_LIMITS={"login_ip": (10, 60)})
def test_auth_rate_limit_opportunistically_prunes_only_stale_fixed_windows():
    now = timezone.now()
    stale = AuthRateLimitBucket.objects.create(
        scope="login_ip",
        key_digest="a" * 64,
        window_started_at=now - timedelta(minutes=5),
        request_count=1,
    )
    recent = AuthRateLimitBucket.objects.create(
        scope="login_ip",
        key_digest="b" * 64,
        window_started_at=now - timedelta(seconds=90),
        request_count=1,
    )

    consume_auth_rate_limit(scope="login_ip", value="203.0.113.10", at=now)

    assert not AuthRateLimitBucket.objects.filter(pk=stale.pk).exists()
    assert AuthRateLimitBucket.objects.filter(pk=recent.pk).exists()


@override_settings(
    AUTH_RATE_LIMITS={
        "password_account_ip": (100, 60),
        "password_account_user": (1, 60),
    }
)
def test_password_change_rate_limit_is_shared_by_user_and_returns_retry_after():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    first = json_mutation(
        client,
        "/api/auth/password/change/",
        {
            "current_password": "wrong-password",
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        },
    )
    limited = json_mutation(
        client,
        "/api/auth/password/change/",
        {
            "current_password": PASSWORD,
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        },
    )

    assert first.status_code == 400
    assert limited.status_code == 429
    assert 1 <= int(limited.headers["Retry-After"]) <= 60
    assert_private(limited)
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/auth/login/", {"email": "reader@example.com", "password": PASSWORD}),
        ("/api/auth/password/reset/", {"email": "reader@example.com"}),
    ],
)
def test_cross_session_csrf_is_rejected_for_unauthenticated_auth_mutations(path, payload):
    issuer = Client(enforce_csrf_checks=True)
    foreign_token = csrf(issuer)
    other = Client(enforce_csrf_checks=True)
    rejected = json_mutation(other, path, payload, token=foreign_token)

    assert rejected.status_code == 403
    assert rejected.json() == {"detail": "CSRF verification failed."}
    assert_private(rejected)


def test_cross_session_csrf_is_rejected_for_reset_confirmation_and_password_change():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
    )
    event = queue_auth_email(user=user, purpose=AuthCredential.Purpose.PASSWORD_RESET)
    raw = issue_credential(event.credential)
    issuer = Client(enforce_csrf_checks=True)
    foreign_token = csrf(issuer)

    reset_client = Client(enforce_csrf_checks=True)
    reset = json_mutation(
        reset_client,
        "/api/auth/password/reset/confirm/",
        {
            "credential": raw,
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        },
        token=foreign_token,
    )

    change_client = Client(enforce_csrf_checks=True)
    change_client.force_login(user)
    change = json_mutation(
        change_client,
        "/api/auth/password/change/",
        {
            "current_password": PASSWORD,
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        },
        token=foreign_token,
    )

    assert reset.status_code == change.status_code == 403
    assert reset.json() == change.json() == {"detail": "CSRF verification failed."}
    assert_private(reset)
    assert_private(change)
    event.credential.refresh_from_db()
    user.refresh_from_db()
    assert event.credential.used_at is None
    assert user.check_password(PASSWORD)


def test_cross_origin_and_referer_are_rejected_for_login_and_password_change():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        password=PASSWORD,
    )
    anonymous = Client(enforce_csrf_checks=True)
    token = anonymous.get("/api/me/", secure=True).json()["csrf_token"]
    login = anonymous.post(
        "/api/auth/login/",
        data=json.dumps({"email": user.email, "password": PASSWORD}),
        content_type="application/json",
        secure=True,
        HTTP_X_CSRFTOKEN=token,
        HTTP_ORIGIN="https://evil.example",
    )

    authenticated = Client(enforce_csrf_checks=True)
    authenticated.force_login(user)
    token = authenticated.get("/api/me/", secure=True).json()["csrf_token"]
    change = authenticated.post(
        "/api/auth/password/change/",
        data=json.dumps(
            {
                "current_password": PASSWORD,
                "password": NEW_PASSWORD,
                "password_confirmation": NEW_PASSWORD,
            }
        ),
        content_type="application/json",
        secure=True,
        HTTP_X_CSRFTOKEN=token,
        HTTP_REFERER="https://evil.example/account",
    )

    assert login.status_code == change.status_code == 403
    assert login.json() == change.json() == {"detail": "CSRF verification failed."}
    assert_private(login)
    assert_private(change)


@pytest.mark.parametrize("prefix", ["/api/auth/", "/api/v1/auth/"])
def test_unknown_auth_api_is_an_ordinary_404(prefix):
    response = Client().post(
        f"{prefix}not-a-real-route/",
        data=b"{}",
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "suffix",
    [
        "logout/",
        "signup/",
        "login/",
        "verify-email/",
        "verify-email/resend/",
        "password/reset/",
        "password/reset/confirm/",
        "password/set/",
        "password/change/",
        "profile/",
    ],
)
def test_versioned_auth_routes_preserve_the_legacy_view_contract(suffix):
    legacy = resolve(f"/api/auth/{suffix}")
    versioned = resolve(f"/api/v1/auth/{suffix}")

    assert versioned.func.view_class is legacy.func.view_class
