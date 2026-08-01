from django import forms

from apps.users.identity import InvalidNickname
from apps.users.services import normalize_public_nickname


class LocalSignupFieldsForm(forms.Form):
    nickname = forms.CharField(
        min_length=2,
        max_length=160,
        widget=forms.TextInput(attrs={"autocomplete": "nickname"}),
    )

    def clean_nickname(self):
        try:
            return normalize_public_nickname(self.cleaned_data["nickname"]).display
        except InvalidNickname as error:
            messages = error.message_dict.get("nickname", error.messages)
            raise forms.ValidationError(messages) from None

    def signup(self, request, user):
        # The account adapter commits the normalized nickname atomically with
        # the allauth-owned user and EmailAddress signup flow.
        return None
