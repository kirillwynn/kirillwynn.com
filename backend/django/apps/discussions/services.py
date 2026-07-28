import math
import unicodedata

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.discussions.models import Comment, CommentRateLimitBucket

MAX_COMMENT_LENGTH = 5000
_DANGEROUS_FORMAT_CONTROLS = {
    "\u061c",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}


def _is_forbidden_scalar(code_point):
    return (
        0xD800 <= code_point <= 0xDFFF
        or 0xFDD0 <= code_point <= 0xFDEF
        or (code_point & 0xFFFF) in {0xFFFE, 0xFFFF}
    )


class RateLimitExceeded(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, math.ceil(retry_after))
        super().__init__("Comment mutation rate limit exceeded.")


def normalize_comment_body(value):
    if not isinstance(value, str):
        raise ValidationError({"body": "This field must be a string."})
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValidationError({"body": "Comment body cannot be empty."})
    if len(normalized) > MAX_COMMENT_LENGTH:
        raise ValidationError(
            {"body": f"Comment body cannot exceed {MAX_COMMENT_LENGTH} Unicode code points."}
        )
    for character in normalized:
        code_point = ord(character)
        if character != "\n" and (
            unicodedata.category(character) == "Cc"
            or character in _DANGEROUS_FORMAT_CONTROLS
            or code_point == 0
            or _is_forbidden_scalar(code_point)
        ):
            raise ValidationError({"body": "Comment body contains a forbidden control character."})
    return normalized


def ensure_can_interact(user):
    if not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")
    if not user.is_active:
        raise PermissionDenied("This account is inactive.")
    if user.is_banned:
        raise PermissionDenied("This account is read-only.")


def _rate_policy(scope):
    if scope == CommentRateLimitBucket.Scope.CREATE:
        return (
            settings.COMMENT_CREATE_RATE_LIMIT_COUNT,
            settings.COMMENT_CREATE_RATE_LIMIT_WINDOW_SECONDS,
        )
    return (
        settings.COMMENT_MUTATION_RATE_LIMIT_COUNT,
        settings.COMMENT_MUTATION_RATE_LIMIT_WINDOW_SECONDS,
    )


def consume_comment_rate_limit(*, user, scope, at=None):
    limit, window_seconds = _rate_policy(scope)
    now = at or timezone.now()
    with transaction.atomic():
        try:
            bucket = CommentRateLimitBucket.objects.select_for_update().get(
                user=user,
                scope=scope,
            )
        except CommentRateLimitBucket.DoesNotExist:
            try:
                with transaction.atomic():
                    bucket = CommentRateLimitBucket.objects.create(
                        user=user,
                        scope=scope,
                        window_started_at=now,
                        request_count=0,
                    )
            except IntegrityError:
                bucket = CommentRateLimitBucket.objects.select_for_update().get(
                    user=user,
                    scope=scope,
                )

        elapsed = (now - bucket.window_started_at).total_seconds()
        if elapsed >= window_seconds or elapsed < 0:
            bucket.window_started_at = now
            bucket.request_count = 0
        elif bucket.request_count >= limit:
            raise RateLimitExceeded(window_seconds - elapsed)

        bucket.request_count += 1
        bucket.save(update_fields=("window_started_at", "request_count"))


@transaction.atomic
def create_top_level_comment(*, post, author, body):
    ensure_can_interact(author)
    comment = Comment(
        post=post,
        author=author,
        body=normalize_comment_body(body),
    )
    comment.full_clean()
    comment.save()
    return comment


@transaction.atomic
def create_reply(*, target_id, author, body):
    ensure_can_interact(author)
    target = (
        Comment.objects.select_for_update()
        .select_related("thread_root", "post", "author")
        .get(pk=target_id)
    )
    root = target.thread_root or target
    if root.pk != target.pk:
        root = Comment.objects.select_for_update().select_related("post", "author").get(pk=root.pk)
    if root.thread_root_id is not None:
        raise ValidationError({"thread_root": "The selected thread root is invalid."})
    if root.moderation_state == Comment.ModerationState.HIDDEN:
        raise PermissionDenied("Replies are disabled for a hidden thread.")
    if target.moderation_state == Comment.ModerationState.HIDDEN:
        raise PermissionDenied("Cannot reply to a hidden comment.")

    reply = Comment(
        post=root.post,
        author=author,
        thread_root=root,
        reply_to_user=target.author,
        body=normalize_comment_body(body),
    )
    reply.full_clean()
    reply.save()
    return reply


@transaction.atomic
def edit_comment(*, comment_id, actor, body):
    ensure_can_interact(actor)
    comment = Comment.objects.select_for_update().select_related("author").get(pk=comment_id)
    if comment.author_id != actor.pk:
        raise PermissionDenied("Only the author can edit this comment.")
    if comment.deleted_at is not None:
        raise ValidationError({"detail": "Deleted comments cannot be edited."})
    if comment.moderation_state == Comment.ModerationState.HIDDEN:
        raise ValidationError({"detail": "Hidden comments cannot be edited."})

    normalized = normalize_comment_body(body)
    if normalized == comment.body:
        return comment
    now = timezone.now()
    comment.body = normalized
    comment.edited_at = now
    comment.save(update_fields=("body", "edited_at", "updated_at"))
    return comment


@transaction.atomic
def soft_delete_comment(*, comment_id, actor):
    ensure_can_interact(actor)
    comment = Comment.objects.select_for_update().select_related("author").get(pk=comment_id)
    if comment.author_id != actor.pk:
        raise PermissionDenied("Only the author can delete this comment.")
    if comment.deleted_at is None:
        comment.deleted_at = timezone.now()
        comment.save(update_fields=("deleted_at", "updated_at"))
    return comment


@transaction.atomic
def set_comment_hidden(*, comment_id, moderator, hidden, reason=""):
    if not moderator.is_active or not moderator.has_perm("discussions.change_comment"):
        raise PermissionDenied("Administrator moderation permission is required.")
    comment = Comment.objects.select_for_update().get(pk=comment_id)
    if hidden:
        if comment.moderation_state != Comment.ModerationState.HIDDEN:
            comment.moderation_state = Comment.ModerationState.HIDDEN
            comment.moderated_at = timezone.now()
            comment.moderated_by = moderator
        comment.moderation_reason = reason[:500]
    else:
        comment.moderation_state = Comment.ModerationState.VISIBLE
        comment.moderated_at = None
        comment.moderated_by = None
        comment.moderation_reason = ""
    comment.full_clean()
    comment.save(
        update_fields=(
            "moderation_state",
            "moderated_at",
            "moderated_by",
            "moderation_reason",
            "updated_at",
        )
    )
    return comment
