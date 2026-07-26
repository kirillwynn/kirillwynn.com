from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.models import User


@admin.register(User)
class ProjectUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Moderation", {"fields": ("is_banned",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Moderation", {"fields": ("is_banned",)}),)
