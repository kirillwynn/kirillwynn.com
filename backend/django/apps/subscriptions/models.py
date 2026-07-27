import uuid

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

MAX_EMAIL_LENGTH = 320


def normalize_email_address(value):
    """Return the trimmed source form and one case-insensitive ASCII key."""

    if not isinstance(value, str):
        raise ValidationError({"email": "Enter a valid email address."})
    source = value.strip()
    if not source or len(source) > MAX_EMAIL_LENGTH or source.count("@") != 1:
        raise ValidationError({"email": "Enter a valid email address."})
    try:
        validate_email(source)
        local, domain = source.rsplit("@", 1)
        ascii_domain = domain.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValidationError):
        raise ValidationError({"email": "Enter a valid email address."}) from None
    canonical = f"{local.casefold()}@{ascii_domain}"
    if len(canonical) > MAX_EMAIL_LENGTH:
        raise ValidationError({"email": "Enter a valid email address."})
    try:
        validate_email(canonical)
    except ValidationError:
        raise ValidationError({"email": "Enter a valid email address."}) from None
    return source, canonical


class Subscriber(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending confirmation"
        ACTIVE = "active", "Active"
        UNSUBSCRIBED = "unsubscribed", "Unsubscribed"
        SUPPRESSED = "suppressed", "Suppressed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=MAX_EMAIL_LENGTH)
    canonical_email = models.CharField(max_length=MAX_EMAIL_LENGTH, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    suppressed_at = models.DateTimeField(null=True, blank=True)
    confirmation_token_version = models.PositiveIntegerField(default=1)
    unsubscribe_token_version = models.PositiveIntegerField(default=1)
    suppression_reason = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ("-created_at", "id")
        constraints = [
            models.UniqueConstraint(
                Lower("canonical_email"),
                name="subscriptions_unique_canonical_email_ci",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="pending",
                        confirmed_at__isnull=True,
                        unsubscribed_at__isnull=True,
                        suppressed_at__isnull=True,
                        suppression_reason="",
                    )
                    | Q(
                        status="active",
                        confirmed_at__isnull=False,
                        unsubscribed_at__isnull=True,
                        suppressed_at__isnull=True,
                        suppression_reason="",
                    )
                    | Q(
                        status="unsubscribed",
                        unsubscribed_at__isnull=False,
                        suppressed_at__isnull=True,
                        suppression_reason="",
                    )
                    | (
                        Q(
                            status="suppressed",
                            unsubscribed_at__isnull=True,
                            suppressed_at__isnull=False,
                        )
                        & ~Q(suppression_reason="")
                    )
                ),
                name="subscriptions_subscriber_lifecycle_shape",
            ),
        ]
        indexes = [
            models.Index(
                fields=("status", "confirmed_at", "id"),
                name="subscriptions_audience_idx",
            ),
            models.Index(fields=("created_at", "id"), name="subscriptions_created_idx"),
        ]

    def clean(self):
        super().clean()
        self.email, self.canonical_email = normalize_email_address(self.email)

    def save(self, *args, **kwargs):
        self.email, self.canonical_email = normalize_email_address(self.email)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class EmailOutbox(models.Model):
    class MessageType(models.TextChoices):
        CONFIRMATION = "confirmation", "Subscription confirmation"
        PUBLICATION = "publication", "New publication"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DELIVERED = "delivered", "Delivered to provider"
        FAILED = "failed", "Terminal failure"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message_type = models.CharField(max_length=20, choices=MessageType.choices)
    subscriber = models.ForeignKey(
        Subscriber,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="outbox_events",
    )
    post = models.ForeignKey(
        "blog.BlogPostPage",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="email_outbox_events",
    )
    audience_cutoff = models.DateTimeField(null=True, blank=True, editable=False)
    credential_version = models.PositiveIntegerField(null=True, blank=True, editable=False)
    message_schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    snapshot_from_email = models.CharField(max_length=320, editable=False)
    snapshot_site_url = models.CharField(max_length=2_048, editable=False)
    snapshot_subject = models.CharField(max_length=255, editable=False)
    snapshot_post_title = models.CharField(max_length=255, blank=True, editable=False)
    snapshot_post_excerpt = models.TextField(blank=True, editable=False)
    snapshot_post_url = models.CharField(max_length=2_048, blank=True, editable=False)
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
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        message_type="confirmation",
                        subscriber__isnull=False,
                        post__isnull=True,
                        audience_cutoff__isnull=True,
                        credential_version__isnull=False,
                        snapshot_post_title="",
                        snapshot_post_excerpt="",
                        snapshot_post_url="",
                    )
                    | Q(
                        message_type="publication",
                        subscriber__isnull=True,
                        post__isnull=False,
                        audience_cutoff__isnull=False,
                        credential_version__isnull=True,
                    )
                    & ~Q(snapshot_post_title="")
                    & ~Q(snapshot_post_excerpt="")
                    & ~Q(snapshot_post_url="")
                )
                & ~Q(snapshot_from_email="")
                & ~Q(snapshot_site_url="")
                & ~Q(snapshot_subject=""),
                name="subscriptions_outbox_message_shape",
            ),
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
                name="subscriptions_outbox_status_shape",
            ),
            models.UniqueConstraint(
                fields=("post",),
                condition=Q(message_type="publication"),
                name="subscriptions_one_publication_event_per_post",
            ),
        ]
        indexes = [
            models.Index(
                fields=("status", "available_at", "created_at", "id"),
                name="subs_outbox_worker_idx",
            )
        ]

    def __str__(self):
        return f"{self.message_type}:{self.pk}"


class EmailDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Accepted by provider"
        DELIVERED = "delivered", "Delivered"
        BOUNCED = "bounced", "Bounced"
        COMPLAINED = "complained", "Complained"
        FAILED = "failed", "Terminal failure"
        SKIPPED = "skipped", "Skipped"
        MANUAL_REVIEW = "manual_review", "Manual review required"

    class AmbiguityReason(models.TextChoices):
        NONE = "", "None"
        TRANSPORT_FAILURE = "transport_failure", "Transport failure"
        CONCURRENT_REQUEST = "concurrent_request", "Concurrent idempotent request"
        PROVIDER_FAILURE = "provider_failure", "Retryable provider failure"
        WINDOW_EXPIRED = "window_expired", "Idempotency window expired"
        PAYLOAD_MISMATCH = "payload_mismatch", "Provider payload mismatch"
        IN_FLIGHT_CANCELLED = "in_flight_cancelled", "Subscriber changed while in flight"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    outbox = models.ForeignKey(
        EmailOutbox,
        on_delete=models.PROTECT,
        related_name="deliveries",
    )
    subscriber = models.ForeignKey(
        Subscriber,
        on_delete=models.PROTECT,
        related_name="deliveries",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    processing_at = models.DateTimeField(null=True, blank=True)
    snapshot_recipient_email = models.CharField(max_length=320, editable=False)
    snapshot_credential_version = models.PositiveIntegerField(editable=False)
    credential_issued_at = models.DateTimeField(editable=False)
    provider_payload_hash = models.CharField(max_length=64, editable=False)
    first_provider_attempt_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_provider_attempt_at = models.DateTimeField(null=True, blank=True, editable=False)
    ambiguity_reason = models.CharField(
        max_length=32,
        choices=AmbiguityReason.choices,
        blank=True,
        default=AmbiguityReason.NONE,
    )
    provider_message_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    provider_created_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    complained_at = models.DateTimeField(null=True, blank=True)
    bounce_type = models.CharField(max_length=64, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("outbox", "subscriber"),
                name="subscriptions_unique_outbox_subscriber",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="pending", processing_at__isnull=True)
                    | Q(status="processing", processing_at__isnull=False)
                    | ~Q(status__in=("pending", "processing"))
                ),
                name="subscriptions_delivery_processing_shape",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        first_provider_attempt_at__isnull=True,
                        last_provider_attempt_at__isnull=True,
                        ambiguity_reason__in=("", "payload_mismatch"),
                    )
                    | Q(
                        first_provider_attempt_at__isnull=False,
                        last_provider_attempt_at__isnull=False,
                        last_provider_attempt_at__gte=F("first_provider_attempt_at"),
                    )
                ),
                name="subscriptions_delivery_attempt_shape",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="manual_review")
                    | (
                        ~Q(ambiguity_reason="")
                        & (
                            Q(first_provider_attempt_at__isnull=False)
                            | Q(ambiguity_reason="payload_mismatch")
                        )
                    )
                ),
                name="subscriptions_delivery_review_shape",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(snapshot_recipient_email="")
                    & ~Q(provider_payload_hash="")
                    & Q(snapshot_credential_version__gte=1)
                ),
                name="subscriptions_delivery_snapshot_shape",
            ),
        ]
        indexes = [
            models.Index(
                fields=("status", "available_at", "created_at", "id"),
                name="subs_delivery_worker_idx",
            ),
            models.Index(
                fields=("outbox", "status", "available_at"),
                name="subs_delivery_outbox_idx",
            ),
            models.Index(
                fields=("status", "first_provider_attempt_at", "id"),
                name="subs_delivery_safety_idx",
            ),
        ]

    @property
    def provider_idempotency_key(self):
        return f"email/{self.pk}"

    def __str__(self):
        return f"{self.outbox.message_type}:{self.pk}"


class EmailWebhookEvent(models.Model):
    class ProcessingState(models.TextChoices):
        PENDING = "pending", "Pending correlation"
        APPLIED = "applied", "Applied"
        IGNORED = "ignored", "Ignored"

    id = models.BigAutoField(primary_key=True)
    provider = models.CharField(max_length=32, default="resend", editable=False)
    event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=80)
    provider_message_id = models.CharField(max_length=255, null=True, blank=True)
    bounce_type = models.CharField(max_length=64, blank=True)
    processing_state = models.CharField(
        max_length=16,
        choices=ProcessingState.choices,
        default=ProcessingState.PENDING,
    )
    delivery = models.ForeignKey(
        EmailDelivery,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="webhook_events",
    )
    provider_occurred_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "event_id"),
                name="subscriptions_unique_provider_event",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        processing_state="pending",
                        provider_message_id__isnull=False,
                        delivery__isnull=True,
                        applied_at__isnull=True,
                    )
                    | Q(
                        processing_state="applied",
                        provider_message_id__isnull=False,
                        delivery__isnull=False,
                        applied_at__isnull=False,
                    )
                    | Q(
                        processing_state="ignored",
                        delivery__isnull=True,
                        applied_at__isnull=False,
                    )
                ),
                name="subscriptions_webhook_processing_shape",
            ),
        ]
        indexes = [
            models.Index(
                fields=("provider", "event_type", "processed_at"),
                name="subscriptions_webhook_type_idx",
            ),
            models.Index(
                fields=("processing_state", "expires_at", "provider_message_id", "id"),
                name="subs_webhook_pending_idx",
            ),
        ]


class SubscriptionRateLimitBucket(models.Model):
    class Scope(models.TextChoices):
        SUBSCRIBE_EMAIL = "subscribe_email", "Subscribe email"
        SUBSCRIBE_IP = "subscribe_ip", "Subscribe IP"
        CONFIRM_IP = "confirm_ip", "Confirm IP"

    scope = models.CharField(max_length=24, choices=Scope.choices)
    key_hash = models.CharField(max_length=64)
    window_started_at = models.DateTimeField()
    request_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("scope", "key_hash"),
                name="subscriptions_unique_rate_bucket",
            )
        ]
