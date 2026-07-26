from django.contrib import admin, messages

from apps.discussions.models import (
    Comment,
    CommentRateLimitBucket,
    CommentReaction,
    PostReaction,
    ReactionRateLimitBucket,
)
from apps.discussions.services import set_comment_hidden


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "author",
        "thread_root",
        "public_status",
        "created_at",
    )
    list_filter = ("moderation_state", "deleted_at", "created_at")
    search_fields = ("body", "author__username", "author__email", "post__title")
    readonly_fields = (
        "post",
        "author",
        "thread_root",
        "reply_to_user",
        "body",
        "created_at",
        "updated_at",
        "edited_at",
        "deleted_at",
        "moderation_state",
        "moderated_at",
        "moderated_by",
        "moderation_reason",
    )
    actions = ("hide_comments", "unhide_comments")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Hide selected comments")
    def hide_comments(self, request, queryset):
        for comment_id in queryset.values_list("pk", flat=True):
            set_comment_hidden(comment_id=comment_id, moderator=request.user, hidden=True)
        self.message_user(request, "Selected comments are hidden.", messages.SUCCESS)

    @admin.action(description="Unhide selected comments")
    def unhide_comments(self, request, queryset):
        for comment_id in queryset.values_list("pk", flat=True):
            set_comment_hidden(comment_id=comment_id, moderator=request.user, hidden=False)
        self.message_user(request, "Selected comments are visible.", messages.SUCCESS)


@admin.register(CommentRateLimitBucket)
class CommentRateLimitBucketAdmin(admin.ModelAdmin):
    list_display = ("user", "scope", "window_started_at", "request_count")
    readonly_fields = ("user", "scope", "window_started_at", "request_count")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"} and super().has_change_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return False


class ReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "target", "user", "emoji", "created_at")
    readonly_fields = ("user", "emoji", "created_at")

    @admin.display(description="Target")
    def target(self, obj):
        return getattr(obj, "post", None) or obj.comment

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"} and super().has_change_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(PostReaction, ReactionAdmin)
admin.site.register(CommentReaction, ReactionAdmin)


@admin.register(ReactionRateLimitBucket)
class ReactionRateLimitBucketAdmin(admin.ModelAdmin):
    list_display = ("user", "window_started_at", "request_count")
    readonly_fields = ("user", "window_started_at", "request_count")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"} and super().has_change_permission(
            request, obj
        )

    def has_delete_permission(self, request, obj=None):
        return False
