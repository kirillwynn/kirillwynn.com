import uuid

from django.db import models


class RevalidationEvent(models.Model):
    class Action(models.TextChoices):
        PUBLISHED = "published", "Published"
        UPDATED = "updated", "Updated"
        UNPUBLISHED = "unpublished", "Unpublished"
        EXPIRED = "expired", "Expired"

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DELIVERED = "delivered", "Delivered"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=16, choices=Action.choices)
    page_id = models.PositiveBigIntegerField()
    slug = models.SlugField(max_length=255, allow_unicode=True)
    previous_slug = models.SlugField(max_length=255, blank=True, allow_unicode=True)
    occurred_at = models.DateTimeField()
    state = models.CharField(
        max_length=16,
        choices=State.choices,
        default=State.PENDING,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["state", "created_at"], name="blog_reval_pending_idx"),
            models.Index(fields=["page_id", "created_at"], name="blog_reval_page_idx"),
        ]
