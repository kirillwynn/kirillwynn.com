import math
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from apps.blog.models import BlogPostPage
from apps.blog.services.visibility import public_blog_posts
from apps.discussions.emoji import normalize_emoji
from apps.discussions.models import (
    Comment,
    CommentReaction,
    PostReaction,
    ReactionRateLimitBucket,
)
from apps.discussions.services import ensure_can_interact


class ReactionRateLimitExceeded(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, math.ceil(retry_after))
        super().__init__("Reaction toggle rate limit exceeded.")


class ReactionTargetUnavailable(Exception):
    pass


def consume_reaction_rate_limit(*, user, at=None):
    limit = settings.REACTION_TOGGLE_RATE_LIMIT_COUNT
    window_seconds = settings.REACTION_TOGGLE_RATE_LIMIT_WINDOW_SECONDS
    now = at or timezone.now()
    with transaction.atomic():
        try:
            bucket = ReactionRateLimitBucket.objects.select_for_update().get(user=user)
        except ReactionRateLimitBucket.DoesNotExist:
            try:
                with transaction.atomic():
                    bucket = ReactionRateLimitBucket.objects.create(
                        user=user,
                        window_started_at=now,
                        request_count=0,
                    )
            except IntegrityError:
                bucket = ReactionRateLimitBucket.objects.select_for_update().get(user=user)

        elapsed = (now - bucket.window_started_at).total_seconds()
        if elapsed >= window_seconds or elapsed < 0:
            bucket.window_started_at = now
            bucket.request_count = 0
        elif bucket.request_count >= limit:
            raise ReactionRateLimitExceeded(window_seconds - elapsed)

        bucket.request_count += 1
        bucket.save(update_fields=("window_started_at", "request_count"))


def _toggle(*, model, lookup, create):
    existing = model.objects.filter(**lookup).first()
    if existing is not None:
        existing.delete()
        return False
    try:
        with transaction.atomic():
            model.objects.create(**create)
    except IntegrityError:
        # The target lock serializes application toggles. If an out-of-band
        # writer ignored that lock, the unique constraint still closes the race.
        model.objects.filter(**lookup).delete()
        return False
    return True


@transaction.atomic
def toggle_post_reaction(*, post_id, user, emoji):
    ensure_can_interact(user)
    normalized = normalize_emoji(emoji)
    post = BlogPostPage.objects.select_for_update().get(pk=post_id)
    if not public_blog_posts().filter(pk=post.pk).exists():
        raise ReactionTargetUnavailable
    consume_reaction_rate_limit(user=user)
    added = _toggle(
        model=PostReaction,
        lookup={"post": post, "user": user, "emoji": normalized},
        create={"post": post, "user": user, "emoji": normalized},
    )
    return post, added


@transaction.atomic
def toggle_comment_reaction(*, comment_id, user, emoji):
    ensure_can_interact(user)
    normalized = normalize_emoji(emoji)
    comment = (
        Comment.objects.select_for_update(of=("self",)).select_related("post").get(pk=comment_id)
    )
    if not public_blog_posts().filter(pk=comment.post_id).exists():
        raise ReactionTargetUnavailable
    if comment.public_status != "visible":
        raise PermissionDenied("Deleted or hidden comments cannot receive reactions.")
    consume_reaction_rate_limit(user=user)
    added = _toggle(
        model=CommentReaction,
        lookup={"comment": comment, "user": user, "emoji": normalized},
        create={"comment": comment, "user": user, "emoji": normalized},
    )
    return comment, added


def _groups(*, model, target_field, target_ids, viewer, participants_path):
    grouped = {target_id: [] for target_id in target_ids}
    if not grouped:
        return grouped

    rows = (
        model.objects.filter(**{f"{target_field}__in": grouped})
        .values(target_field, "emoji")
        .annotate(count=Count("id"))
        .order_by(target_field)
    )
    viewer_reactions = set()
    if viewer.is_authenticated:
        viewer_reactions = set(
            model.objects.filter(
                **{f"{target_field}__in": grouped},
                user=viewer,
            ).values_list(target_field, "emoji")
        )
    for row in rows:
        target_id = row[target_field]
        emoji_value = row["emoji"]
        grouped[target_id].append(
            {
                "emoji": emoji_value,
                "count": row["count"],
                "viewer_reacted": (target_id, emoji_value) in viewer_reactions,
                "participants": participants_path(target_id, emoji_value),
            }
        )
    for groups in grouped.values():
        groups.sort(key=lambda group: group["emoji"])
    return grouped


def post_reaction_groups_for_post(post, *, viewer):
    grouped = _groups(
        model=PostReaction,
        target_field="post_id",
        target_ids=[post.pk],
        viewer=viewer,
        participants_path=lambda _post_id, emoji_value: (
            f"/api/v1/posts/{quote(post.slug)}/reactions/"
            f"{quote(emoji_value, safe='')}/participants/"
        ),
    )
    return grouped[post.pk]


def comment_reaction_groups(comments, *, viewer):
    visible_ids = [comment.pk for comment in comments if comment.public_status == "visible"]
    grouped = _groups(
        model=CommentReaction,
        target_field="comment_id",
        target_ids=visible_ids,
        viewer=viewer,
        participants_path=lambda comment_id, emoji_value: (
            f"/api/v1/comments/{comment_id}/reactions/{quote(emoji_value, safe='')}/participants/"
        ),
    )
    return {comment.pk: grouped.get(comment.pk, []) for comment in comments}
