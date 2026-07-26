from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.models import User


@admin.register(User)
class ProjectUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Moderation", {"fields": ("is_banned",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Moderation", {"fields": ("is_banned",)}),)
    actions = ("ban_users", "unban_users")

    @admin.action(description="Ban selected users")
    def ban_users(self, request, queryset):
        queryset.update(is_banned=True)

    @admin.action(description="Unban selected users")
    def unban_users(self, request, queryset):
        queryset.update(is_banned=False)
