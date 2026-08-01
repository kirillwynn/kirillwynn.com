import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(max_length=320, unique=True)
    # These fields stay nullable for the expand/activate rollout. The Stage 16
    # application digest can therefore continue creating OAuth users while the
    # expansion schema is live.
    email_normalized = models.CharField(
        max_length=320,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    nickname = models.CharField(max_length=160, null=True, blank=True)
    nickname_normalized = models.CharField(
        max_length=160,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    # Persistent database defaults are part of the expand/activate contract:
    # an older Django digest does not name these columns in INSERT statements.
    nickname_confirmed = models.BooleanField(default=False, db_default=False)
    nickname_changed_at = models.DateTimeField(null=True, blank=True, editable=False)
    auth_state_version = models.PositiveIntegerField(default=1, db_default=1, editable=False)
    is_site_author = models.BooleanField(default=False, db_default=False, editable=False)
    is_banned = models.BooleanField(
        default=False,
        help_text="Banned users keep historical content but cannot create or change public data.",
    )

    _AUTH_STATE_FIELDS = frozenset(
        {"password", "email", "email_normalized", "is_active", "is_banned"}
    )

    class Meta(AbstractUser.Meta):
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        nickname__isnull=True,
                        nickname_normalized__isnull=True,
                        nickname_confirmed=False,
                    )
                    | (
                        Q(nickname__isnull=False, nickname_normalized__isnull=False)
                        & ~Q(nickname="")
                        & ~Q(nickname_normalized="")
                    )
                ),
                name="users_nickname_rollout_shape",
            ),
            models.CheckConstraint(
                condition=Q(nickname_changed_at__isnull=True) | Q(nickname_confirmed=True),
                name="users_nickname_change_confirmed",
            ),
            models.CheckConstraint(
                condition=Q(email_normalized__isnull=True) | ~Q(email_normalized=""),
                name="users_email_key_nonempty",
            ),
            models.UniqueConstraint(
                fields=("is_site_author",),
                condition=Q(is_site_author=True),
                name="users_single_site_author",
            ),
        ]

    def save(self, *args, **kwargs):
        """Revoke purpose-bound credentials on security-state changes.

        Public flows already advance ``auth_state_version`` explicitly. This
        model boundary also covers Django Admin password changes and other
        supported ``save()`` callers, so an older credential cannot become
        valid again after a later state reversal.
        """

        update_fields = kwargs.get("update_fields")
        tracked_update = update_fields is None or bool(
            self._AUTH_STATE_FIELDS.intersection(update_fields)
        )
        state_changed = False
        using = kwargs.get("using") or self._state.db or "default"
        if self.pk and tracked_update:
            previous = (
                type(self)
                .objects.using(using)
                .filter(pk=self.pk)
                .values(
                    "password",
                    "email",
                    "email_normalized",
                    "is_active",
                    "is_banned",
                    "auth_state_version",
                )
                .first()
            )
            state_changed = bool(
                previous
                and any(
                    previous[field] != getattr(self, field) for field in self._AUTH_STATE_FIELDS
                )
            )
            if (
                state_changed
                and previous
                and self.auth_state_version <= previous["auth_state_version"]
            ):
                self.auth_state_version = previous["auth_state_version"] + 1
                if update_fields is not None:
                    kwargs["update_fields"] = tuple(
                        dict.fromkeys((*update_fields, "auth_state_version"))
                    )

        result = super().save(*args, **kwargs)
        if state_changed:
            AuthCredential.objects.using(using).filter(
                user_id=self.pk,
                used_at__isnull=True,
                revoked_at__isnull=True,
            ).update(revoked_at=timezone.now())
        return result

    def __str__(self) -> str:
        # Admin/Wagtail may render users created during the expansion window,
        # hence the private compatibility fallback. Public serializers use
        # public_display_name() and never reach this fallback.
        return self.nickname or self.email or self.username

    def get_full_name(self) -> str:
        """Expose the authoritative public identity to Django/Wagtail UI helpers."""

        return self.nickname or ""

    def get_short_name(self) -> str:
        return self.nickname or ""


class NicknameHistory(models.Model):
    class ChangeKind(models.TextChoices):
        BACKFILL = "backfill", "Migration backfill"
        INITIAL = "initial", "Initial selection"
        CHANGE = "change", "User change"
        STAFF_OVERRIDE = "staff_override", "Staff override"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="nickname_history",
    )
    nickname = models.CharField(max_length=160)
    nickname_normalized = models.CharField(max_length=160, unique=True, editable=False)
    change_kind = models.CharField(max_length=16, choices=ChangeKind.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="nickname_changes_performed",
    )
    reason = models.CharField(max_length=500, blank=True)
    claimed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("claimed_at", "id")
        indexes = [
            models.Index(fields=("user", "claimed_at"), name="users_nick_history_user_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(nickname="") & ~Q(nickname_normalized=""),
                name="users_nick_history_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    Q(change_kind="staff_override", actor__isnull=False) & ~Q(reason="")
                    | ~Q(change_kind="staff_override")
                ),
                name="users_nick_staff_audit_shape",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.nickname}"


class AuthCredential(models.Model):
    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify email"
        PASSWORD_RESET = "password_reset", "Password reset"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="auth_credentials",
    )
    purpose = models.CharField(max_length=24, choices=Purpose.choices)
    email_normalized = models.CharField(max_length=320, editable=False)
    auth_state_version = models.PositiveIntegerField(editable=False)
    credential_digest = models.CharField(max_length=64, editable=False)
    expires_at = models.DateTimeField(editable=False)
    used_at = models.DateTimeField(null=True, blank=True, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "id")
        indexes = [
            models.Index(
                fields=("user", "purpose", "created_at"),
                name="users_auth_cred_user_idx",
            ),
            models.Index(fields=("expires_at", "id"), name="users_auth_cred_expiry_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(used_at__isnull=True) | Q(revoked_at__isnull=True),
                name="users_auth_cred_single_terminal",
            ),
            models.CheckConstraint(
                condition=~Q(email_normalized="") & ~Q(credential_digest=""),
                name="users_auth_cred_nonempty",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.purpose}:{self.pk}"


class AuthEmailOutbox(models.Model):
    class MessageType(models.TextChoices):
        EMAIL_VERIFICATION = "email_verification", "Account email verification"
        PASSWORD_RESET = "password_reset", "Account password reset"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DELIVERED = "delivered", "Delivered to provider"
        FAILED = "failed", "Terminal failure"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message_type = models.CharField(max_length=24, choices=MessageType.choices)
    credential = models.OneToOneField(
        AuthCredential,
        on_delete=models.PROTECT,
        related_name="email_event",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="auth_email_events",
    )
    message_schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    snapshot_recipient_email = models.CharField(max_length=320, editable=False)
    snapshot_from_email = models.CharField(max_length=512, editable=False)
    snapshot_site_url = models.CharField(max_length=2_048, editable=False)
    snapshot_subject = models.CharField(max_length=200, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    processing_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    idempotency_key = models.CharField(max_length=200, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=("status", "available_at", "created_at", "id"),
                name="users_auth_outbox_worker_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        status="pending",
                        processing_at__isnull=True,
                        delivered_at__isnull=True,
                    )
                    | Q(
                        status="processing",
                        processing_at__isnull=False,
                        delivered_at__isnull=True,
                    )
                    | Q(status="delivered", delivered_at__isnull=False)
                    | Q(status="failed", delivered_at__isnull=True)
                ),
                name="users_auth_outbox_status_shape",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(snapshot_recipient_email="")
                    & ~Q(snapshot_from_email="")
                    & ~Q(snapshot_site_url="")
                    & ~Q(snapshot_subject="")
                ),
                name="users_auth_outbox_snapshot_shape",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.message_type}:{self.pk}"


class AuthEmailDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Accepted by provider"
        FAILED = "failed", "Terminal failure"
        MANUAL_REVIEW = "manual_review", "Manual review required"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    outbox = models.OneToOneField(
        AuthEmailOutbox,
        on_delete=models.PROTECT,
        related_name="delivery",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    processing_at = models.DateTimeField(null=True, blank=True)
    provider_contract_id = models.CharField(max_length=128, editable=False)
    provider_serializer_version = models.PositiveSmallIntegerField(editable=False)
    provider_idempotency_namespace = models.CharField(max_length=128, editable=False)
    provider_payload_hash = models.CharField(max_length=64, editable=False)
    first_provider_attempt_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_provider_attempt_at = models.DateTimeField(null=True, blank=True, editable=False)
    provider_message_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    ambiguity_reason = models.CharField(max_length=40, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=("status", "available_at", "created_at", "id"),
                name="users_auth_delivery_worker_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status="pending", processing_at__isnull=True)
                    | Q(status="processing", processing_at__isnull=False)
                    | ~Q(status__in=("pending", "processing"))
                ),
                name="users_auth_delivery_processing",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(provider_contract_id="")
                    & ~Q(provider_idempotency_namespace="")
                    & ~Q(provider_payload_hash="")
                ),
                name="users_auth_delivery_transport",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.outbox_id}:{self.status}"

    @property
    def provider_idempotency_key(self):
        # The provider-visible key carries the attested environment/account
        # namespace as well as the globally unique delivery identity. A
        # restored staging database therefore cannot collide with production
        # provider history even if both environments share an API account.
        return f"{self.provider_idempotency_namespace}/{self.pk.hex}"


class AuthRateLimitBucket(models.Model):
    scope = models.CharField(max_length=40)
    key_digest = models.CharField(max_length=64, editable=False)
    window_started_at = models.DateTimeField()
    request_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("scope", "key_digest", "window_started_at"),
                name="users_auth_rate_bucket_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=("scope", "window_started_at"),
                name="users_auth_rate_window_idx",
            ),
        ]
