from django import forms
from django.db import transaction
from wagtail.users.forms import (
    UserCreationForm as WagtailUserCreationForm,
)
from wagtail.users.forms import UserEditForm as WagtailUserEditForm

from apps.users.identity import InvalidNickname, normalize_email_address
from apps.users.models import NicknameHistory
from apps.users.services import normalize_public_nickname


class Stage17WagtailUserCreationForm(WagtailUserCreationForm):
    nickname = forms.CharField(min_length=2, max_length=160, label="Public nickname")

    class Meta(WagtailUserCreationForm.Meta):
        fields = WagtailUserCreationForm.Meta.fields | {"nickname"}

    def clean_email(self):
        return normalize_email_address(self.cleaned_data["email"])[1]

    def clean_nickname(self):
        try:
            return normalize_public_nickname(self.cleaned_data["nickname"]).display
        except InvalidNickname as error:
            raise forms.ValidationError(error.messages) from None

    def save(self, commit=True):
        user = super().save(commit=False)
        canonical = normalize_email_address(self.cleaned_data["email"])[1]
        normalized = normalize_public_nickname(self.cleaned_data["nickname"], user=user)
        user.email = canonical
        user.email_normalized = canonical
        user.nickname = normalized.display
        user.nickname_normalized = normalized.key
        user.nickname_confirmed = True
        user.nickname_changed_at = None
        if not commit:
            return user
        with transaction.atomic():
            user.save()
            self.save_m2m()
            NicknameHistory.objects.create(
                user=user,
                nickname=normalized.display,
                nickname_normalized=normalized.key,
                change_kind=NicknameHistory.ChangeKind.INITIAL,
                reason="Account created through Wagtail Admin",
            )
        return user


class Stage17WagtailUserEditForm(WagtailUserEditForm):
    nickname = forms.CharField(
        disabled=True,
        required=True,
        max_length=160,
        label="Public nickname",
        help_text="Change public nicknames through Django Admin so the override is audited.",
    )

    class Meta(WagtailUserEditForm.Meta):
        fields = WagtailUserEditForm.Meta.fields | {"nickname"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].disabled = True
        self.fields["email"].help_text = "Email change is outside Stage 17."
