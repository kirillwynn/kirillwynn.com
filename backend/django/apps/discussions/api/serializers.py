from datetime import UTC

from django.utils import timezone

from apps.discussions.models import Comment


def _timestamp(value):
    if value is None:
        return None
    localized = timezone.localtime(value, UTC)
    return localized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _display_name(user):
    return user.get_full_name().strip() or user.username


def _author(user):
    return {
        "id": user.pk,
        "display_name": _display_name(user),
        "is_site_author": bool(user.is_staff or user.is_superuser),
    }


def serialize_reaction_participant(user):
    return _author(user)


def _can_interact(user):
    return bool(user.is_authenticated and user.is_active and not user.is_banned)


def serialize_comment(comment, *, viewer, reactions=()):
    status = comment.public_status
    root = comment.thread_root if comment.thread_root_id else comment
    can_interact = _can_interact(viewer)
    owns_comment = bool(viewer.is_authenticated and comment.author_id == viewer.pk)
    thread_allows_replies = root.moderation_state != Comment.ModerationState.HIDDEN
    return {
        "id": comment.pk,
        "kind": "reply" if comment.thread_root_id else "comment",
        "body": comment.body if status == "visible" else None,
        "status": status,
        "author": _author(comment.author),
        "thread_root_id": comment.thread_root_id,
        "reply_to": (
            {
                "id": comment.reply_to_user.pk,
                "display_name": _display_name(comment.reply_to_user),
            }
            if comment.reply_to_user_id
            else None
        ),
        "created_at": _timestamp(comment.created_at),
        "updated_at": _timestamp(comment.updated_at),
        "edited_at": _timestamp(comment.edited_at),
        "reply_count": getattr(comment, "reply_count", 0),
        "last_reply_at": _timestamp(getattr(comment, "last_reply_at", None)),
        "reactions": list(reactions) if status == "visible" else [],
        "viewer": {
            "can_edit": (
                can_interact
                and owns_comment
                and comment.deleted_at is None
                and comment.moderation_state == Comment.ModerationState.VISIBLE
            ),
            "can_delete": can_interact and owns_comment and comment.deleted_at is None,
            "can_reply": (
                can_interact
                and thread_allows_replies
                and comment.moderation_state != Comment.ModerationState.HIDDEN
            ),
            "can_react": can_interact and status == "visible",
        },
    }
