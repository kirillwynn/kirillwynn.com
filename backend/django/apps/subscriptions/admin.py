from django.contrib import admin, messages

from apps.subscriptions.models import (
    EmailDelivery,
    EmailOutbox,
    EmailWebhookEvent,
    Subscriber,
    SubscriptionRateLimitBucket,
)
from apps.subscriptions.services import (
    administratively_unsubscribe,
    suppress_subscriber,
    unsuppress_subscriber,
)


class NoDeleteAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Subscriber)
class SubscriberAdmin(NoDeleteAdmin):
    list_display = (
        "email",
        "status",
        "created_at",
        "confirmation_sent_at",
        "confirmed_at",
    )
    list_filter = ("status", "created_at", "confirmed_at")
    search_fields = ("email", "canonical_email")
    fields = (
        "email",
        "status",
        "created_at",
        "confirmation_sent_at",
        "confirmed_at",
        "unsubscribed_at",
        "suppressed_at",
        "suppression_reason",
    )
    readonly_fields = fields
    actions = ("unsubscribe_selected", "suppress_selected", "unsuppress_selected")

    @admin.action(description="Unsubscribe selected subscribers")
    def unsubscribe_selected(self, request, queryset):
        for subscriber_id in queryset.values_list("pk", flat=True):
            administratively_unsubscribe(subscriber_id)
        self.message_user(request, "Selected subscribers were unsubscribed.", messages.SUCCESS)

    @admin.action(description="Suppress selected subscribers")
    def suppress_selected(self, request, queryset):
        for subscriber_id in queryset.values_list("pk", flat=True):
            suppress_subscriber(subscriber_id, reason="administrative")
        self.message_user(request, "Selected subscribers were suppressed.", messages.SUCCESS)

    @admin.action(description="Remove suppression (new opt-in required)")
    def unsuppress_selected(self, request, queryset):
        for subscriber_id in queryset.values_list("pk", flat=True):
            unsuppress_subscriber(subscriber_id)
        self.message_user(
            request,
            "Suppression was removed; subscribers remain unsubscribed until a new opt-in.",
            messages.SUCCESS,
        )


class ReadOnlyHistoryAdmin(NoDeleteAdmin):
    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"} and super().has_change_permission(
            request, obj
        )


@admin.register(EmailOutbox)
class EmailOutboxAdmin(ReadOnlyHistoryAdmin):
    list_display = (
        "id",
        "message_type",
        "status",
        "attempt_count",
        "available_at",
        "created_at",
    )
    list_filter = ("message_type", "status", "created_at")
    search_fields = ("id", "post__title", "subscriber__email")
    readonly_fields = (
        "id",
        "message_type",
        "subscriber",
        "post",
        "audience_cutoff",
        "status",
        "attempt_count",
        "available_at",
        "processing_at",
        "delivered_at",
        "last_error",
        "created_at",
    )
    exclude = ("credential_version", "idempotency_key")


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(ReadOnlyHistoryAdmin):
    list_display = (
        "id",
        "outbox",
        "subscriber",
        "status",
        "attempt_count",
        "sent_at",
        "delivered_at",
    )
    list_filter = ("status", "outbox__message_type", "created_at")
    search_fields = ("id", "subscriber__email", "provider_message_id", "outbox__post__title")
    readonly_fields = (
        "id",
        "outbox",
        "subscriber",
        "status",
        "attempt_count",
        "available_at",
        "processing_at",
        "provider_message_id",
        "provider_created_at",
        "sent_at",
        "delivered_at",
        "bounced_at",
        "complained_at",
        "bounce_type",
        "last_error",
        "created_at",
        "updated_at",
    )


@admin.register(EmailWebhookEvent)
class EmailWebhookEventAdmin(ReadOnlyHistoryAdmin):
    list_display = ("event_id", "event_type", "delivery", "provider_occurred_at", "processed_at")
    list_filter = ("event_type", "processed_at")
    search_fields = ("event_id", "delivery__provider_message_id")
    readonly_fields = (
        "provider",
        "event_id",
        "event_type",
        "delivery",
        "provider_occurred_at",
        "processed_at",
    )


@admin.register(SubscriptionRateLimitBucket)
class SubscriptionRateLimitBucketAdmin(ReadOnlyHistoryAdmin):
    list_display = ("scope", "window_started_at", "request_count")
    list_filter = ("scope",)
    readonly_fields = ("scope", "key_hash", "window_started_at", "request_count")
