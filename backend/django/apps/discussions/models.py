from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import F, Q
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting

from apps.discussions.emoji import normalize_emoji

CATALOG_ID_VALIDATOR = RegexValidator(
    regex=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    message="Use lowercase ASCII letters, numbers, and single hyphens.",
)
SHA256_VALIDATOR = RegexValidator(
    regex=r"^[0-9a-f]{64}$",
    message="Enter a lowercase SHA-256 digest.",
)
ASSET_VERSION_VALIDATOR = RegexValidator(
    regex=r"^sha256-[0-9a-f]{64}$",
    message="Asset versions must be an immutable sha256-<digest> value.",
)
REACTION_STORAGE_KEY_VALIDATOR = RegexValidator(
    regex=(
        r"^reactions/[a-z0-9]+(?:-[a-z0-9]+)*/[0-9a-f]{64}/"
        r"(?:asset\.webp|animation\.gif|poster\.webp)$"
    ),
    message="Use a content-addressed reaction storage key.",
)


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


class ReactionCatalogItem(models.Model):
    class Kind(models.TextChoices):
        STATIC = "static", "Static"
        ANIMATED = "animated", "Animated"

    class ApprovalStatus(models.TextChoices):
        STAGING_ONLY = "staging-only/unverified", "Staging only / unverified"
        PRODUCTION_APPROVED = "production-approved", "Production approved"

    catalog_id = models.SlugField(
        primary_key=True,
        max_length=80,
        validators=[CATALOG_ID_VALIDATOR],
    )
    display_name = models.CharField(max_length=120)
    accessibility_label = models.CharField(max_length=160)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    ordering = models.PositiveIntegerField(unique=True)
    enabled = models.BooleanField(default=False)
    selectable = models.BooleanField(default=False)
    quick_order = models.PositiveSmallIntegerField(null=True, blank=True, unique=True)
    source_sha256 = models.CharField(max_length=64, validators=[SHA256_VALIDATOR])
    normalized_sha256 = models.CharField(max_length=64, validators=[SHA256_VALIDATOR])
    poster_sha256 = models.CharField(
        max_length=64,
        blank=True,
        validators=[SHA256_VALIDATOR],
    )
    immutable_asset_version = models.CharField(
        max_length=71,
        validators=[ASSET_VERSION_VALIDATOR],
    )
    intrinsic_width = models.PositiveSmallIntegerField()
    intrinsic_height = models.PositiveSmallIntegerField()
    frame_count = models.PositiveSmallIntegerField()
    duration_ms = models.PositiveIntegerField()
    minimum_frame_delay_ms = models.PositiveIntegerField()
    asset_storage_key = models.CharField(
        max_length=320,
        unique=True,
        validators=[REACTION_STORAGE_KEY_VALIDATOR],
    )
    poster_storage_key = models.CharField(
        max_length=320,
        blank=True,
        validators=[REACTION_STORAGE_KEY_VALIDATOR],
    )
    provenance_source = models.CharField(max_length=500)
    provenance_author = models.CharField(max_length=200, blank=True)
    license = models.CharField(max_length=200, blank=True)
    rights_basis = models.CharField(max_length=500)
    approval_status = models.CharField(max_length=32, choices=ApprovalStatus.choices)
    manifest_sha256 = models.CharField(max_length=64, validators=[SHA256_VALIDATOR])
    imported_at = models.DateTimeField()

    class Meta:
        ordering = ("ordering", "catalog_id")
        constraints = [
            models.CheckConstraint(
                condition=Q(intrinsic_width__lte=512, intrinsic_height__lte=512),
                name="discussion_catalog_dimensions",
            ),
            models.CheckConstraint(
                condition=Q(frame_count__gte=1, frame_count__lte=160),
                name="discussion_catalog_frame_count",
            ),
            models.CheckConstraint(
                condition=Q(duration_ms__lte=10_000),
                name="discussion_catalog_duration",
            ),
            models.CheckConstraint(
                condition=Q(quick_order__isnull=True) | Q(quick_order__gte=1, quick_order__lte=3),
                name="discussion_catalog_quick_order",
            ),
            models.CheckConstraint(
                condition=Q(selectable=False) | Q(enabled=True),
                name="discussion_catalog_selectable_enabled",
            ),
            models.CheckConstraint(
                condition=Q(quick_order__isnull=True) | Q(enabled=True, selectable=True),
                name="discussion_catalog_quick_selectable",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind="static",
                        frame_count=1,
                        duration_ms=0,
                        minimum_frame_delay_ms=0,
                        poster_sha256="",
                        poster_storage_key="",
                    )
                    | Q(
                        kind="animated",
                        frame_count__gte=2,
                        duration_ms__gt=0,
                        minimum_frame_delay_ms__gt=0,
                    )
                ),
                name="discussion_catalog_kind_metadata",
            ),
        ]

    def clean(self):
        super().clean()
        if self.immutable_asset_version != f"sha256-{self.normalized_sha256}":
            raise ValidationError(
                {
                    "immutable_asset_version": (
                        "The immutable version must identify the normalized asset bytes."
                    )
                }
            )
        expected_directory = f"reactions/{self.catalog_id}/{self.normalized_sha256}/"
        if not self.asset_storage_key.startswith(expected_directory):
            raise ValidationError(
                {"asset_storage_key": "The key must contain this item and normalized hash."}
            )
        if self.kind == self.Kind.STATIC:
            if not self.asset_storage_key.endswith("/asset.webp"):
                raise ValidationError({"asset_storage_key": "Static items must use asset.webp."})
        else:
            if not self.asset_storage_key.endswith("/animation.gif"):
                raise ValidationError(
                    {"asset_storage_key": "Animated items must use animation.gif."}
                )
            expected_poster = f"reactions/{self.catalog_id}/{self.normalized_sha256}/poster.webp"
            if self.poster_storage_key != expected_poster or not self.poster_sha256:
                raise ValidationError(
                    {"poster_storage_key": "Animated items require the attested poster key."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.display_name} ({self.catalog_id})"


class ReactionModel(models.Model):
    emoji = models.CharField(max_length=128, blank=True, default="")
    catalog_item = models.ForeignKey(
        ReactionCatalogItem,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.catalog_item_id is None:
            self.emoji = normalize_emoji(self.emoji)
        elif self.emoji:
            raise ValidationError(
                {"emoji": "Catalog reactions cannot also carry a legacy Unicode value."}
            )

    def save(self, *args, **kwargs):
        if self.catalog_item_id is None:
            self.emoji = normalize_emoji(self.emoji)
        else:
            self.emoji = ""
        return super().save(*args, **kwargs)


class PostReaction(ReactionModel):
    post = models.ForeignKey(
        "blog.BlogPostPage",
        on_delete=models.PROTECT,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="post_reactions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("post", "user", "emoji"),
                name="discussion_unique_post_reaction",
            ),
            models.UniqueConstraint(
                fields=("post", "user", "catalog_item"),
                condition=Q(catalog_item__isnull=False),
                name="discussion_unique_post_catalog_reaction",
            ),
            models.CheckConstraint(
                condition=(Q(emoji="", catalog_item__isnull=False))
                | (~Q(emoji="") & Q(catalog_item__isnull=True)),
                name="discussion_post_reaction_identity",
            ),
        ]
        indexes = [
            models.Index(
                fields=("post", "emoji", "created_at", "id"),
                name="discussion_post_reaction_idx",
            ),
            models.Index(
                fields=("post", "catalog_item", "created_at", "id"),
                name="discuss_post_catalog_react",
            ),
        ]


class CommentReaction(ReactionModel):
    comment = models.ForeignKey(
        Comment,
        on_delete=models.PROTECT,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comment_reactions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("comment", "user", "emoji"),
                name="discussion_unique_comment_reaction",
            ),
            models.UniqueConstraint(
                fields=("comment", "user", "catalog_item"),
                condition=Q(catalog_item__isnull=False),
                name="discussion_unique_comment_catalog_reaction",
            ),
            models.CheckConstraint(
                condition=(Q(emoji="", catalog_item__isnull=False))
                | (~Q(emoji="") & Q(catalog_item__isnull=True)),
                name="discussion_comment_reaction_identity",
            ),
        ]
        indexes = [
            models.Index(
                fields=("comment", "emoji", "created_at", "id"),
                name="discussion_comment_react_idx",
            ),
            models.Index(
                fields=("comment", "catalog_item", "created_at", "id"),
                name="discuss_comment_catalog_react",
            ),
        ]


class ReactionRateLimitBucket(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reaction_rate_limit_bucket",
    )
    window_started_at = models.DateTimeField()
    request_count = models.PositiveIntegerField(default=0)


class ReactionSettings(BaseSiteSetting):
    quick_reaction_one = models.CharField(max_length=128, default="👍")
    quick_reaction_two = models.CharField(max_length=128, default="❤️")
    quick_reaction_three = models.CharField(max_length=128, default="🎉")
    quick_reaction_item_one = models.ForeignKey(
        ReactionCatalogItem,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    quick_reaction_item_two = models.ForeignKey(
        ReactionCatalogItem,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    quick_reaction_item_three = models.ForeignKey(
        ReactionCatalogItem,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    panels = [
        MultiFieldPanel(
            [
                FieldPanel("quick_reaction_item_one"),
                FieldPanel("quick_reaction_item_two"),
                FieldPanel("quick_reaction_item_three"),
            ],
            heading="Custom quick reactions",
        )
    ]

    @property
    def quick_reactions(self):
        return [
            self.quick_reaction_one,
            self.quick_reaction_two,
            self.quick_reaction_three,
        ]

    @property
    def quick_reaction_items(self):
        return [
            self.quick_reaction_item_one,
            self.quick_reaction_item_two,
            self.quick_reaction_item_three,
        ]

    def clean(self):
        super().clean()
        normalized = [normalize_emoji(value) for value in self.quick_reactions]
        if len(set(normalized)) != 3:
            raise ValidationError("Quick reactions must be distinct after normalization.")
        (
            self.quick_reaction_one,
            self.quick_reaction_two,
            self.quick_reaction_three,
        ) = normalized
        custom_ids = [
            self.quick_reaction_item_one_id,
            self.quick_reaction_item_two_id,
            self.quick_reaction_item_three_id,
        ]
        if any(custom_ids):
            if any(value is None for value in custom_ids):
                raise ValidationError("Choose exactly three custom quick reactions.")
            if len(set(custom_ids)) != 3:
                raise ValidationError("Custom quick reactions must be distinct.")
            for item in self.quick_reaction_items:
                if not item.enabled or not item.selectable:
                    raise ValidationError("Custom quick reactions must be enabled and selectable.")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.clean()
            result = super().save(*args, **kwargs)
            custom_ids = [
                self.quick_reaction_item_one_id,
                self.quick_reaction_item_two_id,
                self.quick_reaction_item_three_id,
            ]
            if all(custom_ids):
                ReactionCatalogItem.objects.filter(quick_order__isnull=False).update(
                    quick_order=None
                )
                for quick_order, catalog_id in enumerate(custom_ids, start=1):
                    ReactionCatalogItem.objects.filter(pk=catalog_id).update(
                        quick_order=quick_order
                    )
            return result
