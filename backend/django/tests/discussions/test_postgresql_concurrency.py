from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection

from apps.discussions.models import CommentRateLimitBucket
from apps.discussions.services import (
    consume_comment_rate_limit,
    edit_comment,
    soft_delete_comment,
)

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="Row-locking semantics require PostgreSQL.",
    ),
]


def _run_concurrently(functions):
    barrier = Barrier(len(functions))

    def run(function):
        close_old_connections()
        barrier.wait()
        try:
            return function()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        futures = [executor.submit(run, function) for function in functions]
        return [future.result() for future in futures]


def test_rate_limit_bucket_creation_race_keeps_one_row(user):
    _run_concurrently(
        [
            lambda: consume_comment_rate_limit(
                user=user,
                scope=CommentRateLimitBucket.Scope.CREATE,
            ),
            lambda: consume_comment_rate_limit(
                user=user,
                scope=CommentRateLimitBucket.Scope.CREATE,
            ),
        ]
    )

    bucket = CommentRateLimitBucket.objects.get(
        user=user,
        scope=CommentRateLimitBucket.Scope.CREATE,
    )
    assert bucket.request_count == 2


def test_edit_delete_race_serializes_to_deleted_state(public_post, user):
    from apps.discussions.services import create_top_level_comment

    comment = create_top_level_comment(post=public_post, author=user, body="Original")

    def edit():
        try:
            edit_comment(comment_id=comment.pk, actor=user, body="Changed")
        except ValidationError as error:
            return type(error).__name__
        return "edited"

    results = _run_concurrently(
        [
            edit,
            lambda: (
                soft_delete_comment(comment_id=comment.pk, actor=user),
                "deleted",
            )[1],
        ]
    )

    comment.refresh_from_db()
    assert comment.deleted_at is not None
    assert "deleted" in results
    assert set(results) <= {"deleted", "edited", "ValidationError"}
