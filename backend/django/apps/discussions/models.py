from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Comment(models.Model):
    class ModerationState(models.TextChoices):
        VISIBLE = "visible", "Visible"
        HIDDEN = "hidden", "Hidden"

    post = models.ForeignKey(
        "blog.BlogPostPage",
        on_delete=models.PROTECT,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comments",
    )
    thread_root = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="thread_replies",
    )
    reply_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="comment_mentions",
    )
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    moderation_state = models.CharField(
        max_length=16,
        choices=ModerationState.choices,
        default=ModerationState.VISIBLE,
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="moderated_comments",
    )
    moderation_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("post", "thread_root", "-created_at", "-id"),
                name="discussion_post_roots_idx",
            ),
            models.Index(
                fields=("thread_root", "created_at", "id"),
                name="discussion_thread_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(thread_root__isnull=True) | ~Q(thread_root=F("id")),
                name="discussion_no_self_thread_root",
            ),
            models.CheckConstraint(
                condition=Q(thread_root__isnull=False, reply_to_user__isnull=False)
                | Q(thread_root__isnull=True, reply_to_user__isnull=True),
                name="discussion_reply_shape",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        moderation_state="visible",
                        moderated_at__isnull=True,
                        moderated_by__isnull=True,
                    )
                    | Q(
                        moderation_state="hidden",
                        moderated_at__isnull=False,
                        moderated_by__isnull=False,
                    )
                ),
                name="discussion_moderation_shape",
            ),
        ]

    @property
    def is_reply(self):
        return self.thread_root_id is not None

    @property
    def public_status(self):
        if self.deleted_at is not None:
            return "deleted"
        if self.moderation_state == self.ModerationState.HIDDEN:
            return "hidden"
        return "visible"

    def clean(self):
        super().clean()
        if self.thread_root_id is None:
            if self.reply_to_user_id is not None:
                raise ValidationError(
                    {"reply_to_user": "Top-level comments cannot mention a reply target."}
                )
            return
        if self.pk is not None and self.thread_root_id == self.pk:
            raise ValidationError({"thread_root": "A comment cannot be its own thread root."})
        root = self.thread_root
        if root.thread_root_id is not None:
            raise ValidationError(
                {"thread_root": "Replies must point directly to a top-level comment."}
            )
        if self.post_id != root.post_id:
            raise ValidationError(
                {"thread_root": "A reply and its root must belong to the same post."}
            )

    def __str__(self):
        return f"Comment {self.pk or 'unsaved'} by {self.author}"


class CommentRateLimitBucket(models.Model):
    class Scope(models.TextChoices):
        CREATE = "create", "Create or reply"
        MUTATION = "mutation", "Edit or delete"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_rate_limit_buckets",
    )
    scope = models.CharField(max_length=16, choices=Scope.choices)
    window_started_at = models.DateTimeField()
    request_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "scope"),
                name="discussion_unique_rate_bucket",
            )
        ]
