import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import Client

from apps.users.models import AuthRateLimitBucket, NicknameHistory, User
from apps.users.rate_limits import AuthRateLimitExceeded, consume_auth_rate_limit
from apps.users.services import change_nickname
from tests.identity import create_identity_user

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.postgresql,
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="Identity uniqueness races require PostgreSQL.",
    ),
]

PASSWORD = "Stage17!concurrent-passphrase"


def _run_concurrently(functions):
    barrier = Barrier(len(functions))

    def run(function):
        close_old_connections()
        barrier.wait()
        try:
            try:
                return function()
            except Exception as error:
                return error
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = [executor.submit(run, function) for function in functions]
        return [future.result() for future in futures]


def _signup(email, nickname):
    response = Client().post(
        "/api/auth/signup/",
        data=json.dumps(
            {
                "email": email,
                "nickname": nickname,
                "password": PASSWORD,
                "password_confirmation": PASSWORD,
            }
        ),
        content_type="application/json",
    )
    return response.status_code, response.json()


def test_parallel_case_variant_signup_creates_exactly_one_identity():
    results = _run_concurrently(
        [
            lambda: _signup("Concurrent@Example.com", "Concurrent One"),
            lambda: _signup("concurrent@example.COM", "Concurrent Two"),
        ]
    )

    assert [result[0] for result in results] == [202, 202]
    assert User.objects.filter(email_normalized="concurrent@example.com").count() == 1
    assert NicknameHistory.objects.count() == 1


def test_parallel_signup_nickname_collision_has_one_database_winner():
    results = _run_concurrently(
        [
            lambda: _signup("one@example.com", "Straße Reader"),
            lambda: _signup("two@example.com", "STRASSE Reader"),
        ]
    )

    assert sum(result[0] == 202 for result in results) == 1
    assert sum(result[0] in {400, 409} for result in results) == 1
    assert User.objects.count() == 1
    assert NicknameHistory.objects.filter(nickname_normalized="strasse reader").count() == 1


def test_parallel_users_cannot_claim_the_same_renamed_nickname():
    first = create_identity_user(
        username="first",
        email="first@example.com",
        nickname="First Reader",
    )
    second = create_identity_user(
        username="second",
        email="second@example.com",
        nickname="Second Reader",
    )

    results = _run_concurrently(
        [
            lambda: change_nickname(user=first, nickname="Shared Name").nickname,
            lambda: change_nickname(user=second, nickname="shared name").nickname,
        ]
    )

    assert sum(isinstance(result, ValidationError) for result in results) == 1
    assert sum(isinstance(result, str) for result in results) == 1
    assert User.objects.filter(nickname_normalized="shared name").count() == 1
    assert NicknameHistory.objects.filter(nickname_normalized="shared name").count() == 1


def test_parallel_renames_of_one_user_allow_exactly_one_change_before_cooldown():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Original Reader",
    )

    results = _run_concurrently(
        [
            lambda: change_nickname(user=user, nickname="First Candidate").nickname,
            lambda: change_nickname(user=user, nickname="Second Candidate").nickname,
        ]
    )

    assert sum(isinstance(result, ValidationError) for result in results) == 1
    assert sum(isinstance(result, str) for result in results) == 1
    user.refresh_from_db()
    assert user.nickname in {"First Candidate", "Second Candidate"}
    assert user.nickname_history.count() == 2


def test_parallel_database_rate_limit_allows_exactly_one_request(settings):
    settings.AUTH_RATE_LIMITS = {"concurrent": (1, 60)}
    results = _run_concurrently(
        [
            lambda: consume_auth_rate_limit(scope="concurrent", value="same-key"),
            lambda: consume_auth_rate_limit(scope="concurrent", value="same-key"),
        ]
    )

    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, AuthRateLimitExceeded) for result in results) == 1
    assert AuthRateLimitBucket.objects.get(scope="concurrent").request_count == 1
