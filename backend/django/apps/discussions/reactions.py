import math
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from apps.blog.models import BlogPostPage
from apps.blog.services.visibility import public_blog_posts
from apps.discussions.models import (
    CATALOG_ID_VALIDATOR,
    Comment,
    CommentReaction,
    PostReaction,
    ReactionCatalogItem,
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


def _catalog_item(reaction_id):
    if not isinstance(reaction_id, str) or len(reaction_id) > 80:
        raise ValidationError({"reaction_id": "A catalog ID string is required."})
    try:
        CATALOG_ID_VALIDATOR(reaction_id)
        return ReactionCatalogItem.objects.get(
            catalog_id=reaction_id,
            enabled=True,
            selectable=True,
        )
    except (ReactionCatalogItem.DoesNotExist, ValidationError):
        raise ValidationError({"reaction_id": "Unknown or unavailable reaction ID."}) from None


@transaction.atomic
def toggle_post_reaction(*, post_id, user, reaction_id):
    ensure_can_interact(user)
    post = BlogPostPage.objects.select_for_update().get(pk=post_id)
    if not public_blog_posts().filter(pk=post.pk).exists():
        raise ReactionTargetUnavailable
    item = _catalog_item(reaction_id)
    consume_reaction_rate_limit(user=user)
    added = _toggle(
        model=PostReaction,
        lookup={"post": post, "user": user, "catalog_item": item},
        create={"post": post, "user": user, "catalog_item": item},
    )
    return post, added


@transaction.atomic
def toggle_comment_reaction(*, comment_id, user, reaction_id):
    ensure_can_interact(user)
    comment = (
        Comment.objects.select_for_update(of=("self",)).select_related("post").get(pk=comment_id)
    )
    if not public_blog_posts().filter(pk=comment.post_id).exists():
        raise ReactionTargetUnavailable
    if comment.public_status != "visible":
        raise PermissionDenied("Deleted or hidden comments cannot receive reactions.")
    item = _catalog_item(reaction_id)
    consume_reaction_rate_limit(user=user)
    added = _toggle(
        model=CommentReaction,
        lookup={"comment": comment, "user": user, "catalog_item": item},
        create={"comment": comment, "user": user, "catalog_item": item},
    )
    return comment, added


def reaction_descriptor(item):
    if isinstance(item, dict):

        def value(field):
            return item[f"catalog_item__{field}"]

    else:

        def value(field):
            return getattr(item, field)

    asset_url = default_storage.url(value("asset_storage_key"))
    poster_key = value("poster_storage_key")
    return {
        "id": value("catalog_id"),
        "name": value("display_name"),
        "label": value("accessibility_label"),
        "kind": value("kind"),
        "asset_url": asset_url,
        "poster_url": default_storage.url(poster_key) if poster_key else asset_url,
        "width": value("intrinsic_width"),
        "height": value("intrinsic_height"),
        "version": value("immutable_asset_version"),
    }


CATALOG_GROUP_FIELDS = (
    "catalog_item__catalog_id",
    "catalog_item__display_name",
    "catalog_item__accessibility_label",
    "catalog_item__kind",
    "catalog_item__asset_storage_key",
    "catalog_item__poster_storage_key",
    "catalog_item__intrinsic_width",
    "catalog_item__intrinsic_height",
    "catalog_item__immutable_asset_version",
    "catalog_item__ordering",
)


def _groups(*, model, target_field, target_ids, viewer, participants_path):
    grouped = {target_id: [] for target_id in target_ids}
    if not grouped:
        return grouped

    rows = (
        model.objects.filter(
            **{f"{target_field}__in": grouped},
            catalog_item__enabled=True,
        )
        .values(target_field, *CATALOG_GROUP_FIELDS)
        .annotate(count=Count("id"))
        .order_by(
            target_field,
            "catalog_item__ordering",
            "catalog_item__catalog_id",
        )
    )
    viewer_reactions = set()
    if viewer.is_authenticated:
        viewer_reactions = set(
            model.objects.filter(
                **{f"{target_field}__in": grouped},
                catalog_item__enabled=True,
                user=viewer,
            ).values_list(target_field, "catalog_item__catalog_id")
        )
    for row in rows:
        target_id = row[target_field]
        reaction_id = row["catalog_item__catalog_id"]
        grouped[target_id].append(
            {
                "reaction": reaction_descriptor(row),
                "count": row["count"],
                "viewer_reacted": (target_id, reaction_id) in viewer_reactions,
                "participants": participants_path(target_id, reaction_id),
            }
        )
    return grouped


def post_reaction_groups(posts, *, viewer):
    posts = list(posts)
    slugs_by_id = {post.pk: post.slug for post in posts}
    return _groups(
        model=PostReaction,
        target_field="post_id",
        target_ids=slugs_by_id,
        viewer=viewer,
        participants_path=lambda post_id, reaction_id: (
            f"/api/v1/posts/{quote(slugs_by_id[post_id])}/reactions/{reaction_id}/participants/"
        ),
    )


def post_reaction_groups_for_post(post, *, viewer):
    grouped = post_reaction_groups([post], viewer=viewer)
    return grouped[post.pk]


def comment_reaction_groups(comments, *, viewer):
    visible_ids = [comment.pk for comment in comments if comment.public_status == "visible"]
    grouped = _groups(
        model=CommentReaction,
        target_field="comment_id",
        target_ids=visible_ids,
        viewer=viewer,
        participants_path=lambda comment_id, reaction_id: (
            f"/api/v1/comments/{comment_id}/reactions/{reaction_id}/participants/"
        ),
    )
    return {comment.pk: grouped.get(comment.pk, []) for comment in comments}
