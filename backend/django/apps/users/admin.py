import allauth.account.admin  # noqa: F401  # register before replacing the defaults
import allauth.socialaccount.admin  # noqa: F401  # register before replacing the defaults
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db.models import F
from django.utils import timezone

from apps.users.identity import InvalidNickname, normalize_email_address, normalize_nickname
from apps.users.models import AuthCredential, NicknameHistory, User
from apps.users.services import change_nickname, normalize_public_nickname

# allauth's generic model admins would permit manual email verification/change,
# social identity reassignment, and persisted provider tokens. Keep the first
# two visible for incident review while making their lifecycle flow-owned.
admin.site.unregister(EmailAddress)
admin.site.unregister(SocialAccount)
admin.site.unregister(SocialToken)


class FlowOwnedIdentityAdmin(admin.ModelAdmin):
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailAddress)
class ReadOnlyEmailAddressAdmin(FlowOwnedIdentityAdmin):
    list_display = ("email", "user", "primary", "verified")
    list_select_related = ("user",)
    search_fields = ("email", "user__nickname")
    readonly_fields = ("user", "email", "primary", "verified")


@admin.register(SocialAccount)
class ReadOnlySocialAccountAdmin(FlowOwnedIdentityAdmin):
    list_display = ("provider", "uid", "user", "date_joined", "last_login")
    list_select_related = ("user",)
    search_fields = ("provider", "uid", "user__nickname", "user__email")
    readonly_fields = (
        "user",
        "provider",
        "uid",
        "extra_data",
        "date_joined",
        "last_login",
    )


class ProjectUserCreationForm(UserCreationForm):
    email = forms.EmailField(max_length=254)
    nickname = forms.CharField(min_length=2, max_length=160)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "nickname")

    def clean_email(self):
        return normalize_email_address(self.cleaned_data["email"])[1]

    def clean_nickname(self):
        try:
            return normalize_nickname(
                self.cleaned_data["nickname"],
                allow_reserved=True,
            ).display
        except InvalidNickname as error:
            raise forms.ValidationError(error.messages) from None


class ProjectUserChangeForm(UserChangeForm):
    nickname_override = forms.CharField(required=False, max_length=160)
    nickname_override_reason = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["nickname_override"].initial = self.instance.nickname

    def clean(self):
        cleaned = super().clean()
        override = cleaned.get("nickname_override", "").strip()
        if override and override != (self.instance.nickname or ""):
            if not cleaned.get("nickname_override_reason", "").strip():
                self.add_error(
                    "nickname_override_reason",
                    "A reason is required for a staff nickname override.",
                )
        return cleaned


@admin.register(User)
class ProjectUserAdmin(UserAdmin):
    add_form = ProjectUserCreationForm
    form = ProjectUserChangeForm
    list_display = ("email", "nickname", "is_active", "is_banned", "is_staff")
    readonly_fields = (
        "nickname",
        "nickname_normalized",
        "nickname_confirmed",
        "nickname_changed_at",
        "auth_state_version",
        "is_site_author",
    )
    fieldsets = UserAdmin.fieldsets + (
        (
            "Public identity",
            {
                "fields": (
                    "nickname",
                    "nickname_normalized",
                    "nickname_confirmed",
                    "nickname_changed_at",
                    "nickname_override",
                    "nickname_override_reason",
                    "auth_state_version",
                    "is_site_author",
                )
            },
        ),
        ("Moderation", {"fields": ("is_banned",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "nickname", "password1", "password2"),
            },
        ),
    )
    actions = ("ban_users", "unban_users")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj is None:
            return tuple(field for field in fields if field != "nickname")
        # Email change is deliberately outside Stage 17. Keeping the existing
        # canonical identity immutable also prevents User.email from drifting
        # away from the database-enforced email_normalized key.
        return (*fields, "email")

    def save_model(self, request, obj, form, change):
        if not change:
            canonical = normalize_email_address(form.cleaned_data["email"])[1]
            normalized = normalize_public_nickname(
                form.cleaned_data["nickname"],
                user=obj,
                staff_override=True,
            )
            obj.email = canonical
            obj.email_normalized = canonical
            obj.nickname = normalized.display
            obj.nickname_normalized = normalized.key
            obj.nickname_confirmed = True
            obj.nickname_changed_at = None
            super().save_model(request, obj, form, change)
            NicknameHistory.objects.create(
                user=obj,
                nickname=normalized.display,
                nickname_normalized=normalized.key,
                change_kind=NicknameHistory.ChangeKind.STAFF_OVERRIDE,
                actor=request.user,
                reason="Account created through Django Admin",
            )
            return
        super().save_model(request, obj, form, change)
        override = form.cleaned_data.get("nickname_override", "").strip()
        if override and override != (obj.nickname or ""):
            change_nickname(
                user=obj,
                nickname=override,
                actor=request.user,
                staff_override=True,
                reason=form.cleaned_data["nickname_override_reason"],
            )

    @admin.action(description="Ban selected users")
    def ban_users(self, request, queryset):
        now = timezone.now()
        ids = list(queryset.filter(is_banned=False).values_list("pk", flat=True))
        User.objects.filter(pk__in=ids).update(
            is_banned=True,
            auth_state_version=F("auth_state_version") + 1,
        )
        AuthCredential.objects.filter(
            user_id__in=ids,
            used_at__isnull=True,
            revoked_at__isnull=True,
        ).update(revoked_at=now)

    @admin.action(description="Unban selected users")
    def unban_users(self, request, queryset):
        now = timezone.now()
        ids = list(queryset.filter(is_banned=True).values_list("pk", flat=True))
        User.objects.filter(pk__in=ids).update(
            is_banned=False,
            auth_state_version=F("auth_state_version") + 1,
        )
        AuthCredential.objects.filter(
            user_id__in=ids,
            used_at__isnull=True,
            revoked_at__isnull=True,
        ).update(revoked_at=now)
