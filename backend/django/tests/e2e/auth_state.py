"""Inspect isolated cross-stack identities for the controlled browser suite."""

from __future__ import annotations

import json
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cross_stack")
django.setup()

from apps.users.credentials import issue_credential  # noqa: E402
from apps.users.identity import normalize_email_address  # noqa: E402
from apps.users.models import AuthCredential, User  # noqa: E402
from apps.users.services import has_verified_primary_email, profile_complete  # noqa: E402


def user_for(email: str) -> User:
    canonical = normalize_email_address(email)[1]
    return User.objects.get(email_normalized=canonical)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: auth_state.py verification-credential|reset-credential|status EMAIL"
        )
    action, email = sys.argv[1:]
    user = user_for(email)
    purpose = {
        "verification-credential": AuthCredential.Purpose.VERIFY_EMAIL,
        "reset-credential": AuthCredential.Purpose.PASSWORD_RESET,
    }.get(action)
    if purpose:
        # stdout is captured directly into the Playwright process and is never
        # printed. Successful runs retain no trace or screenshot, while the
        # shared artifact sanitizer removes secrets from failure artifacts.
        credential = AuthCredential.objects.get(
            user=user,
            purpose=purpose,
            used_at__isnull=True,
            revoked_at__isnull=True,
        )
        print(issue_credential(credential), end="")
        return
    if action == "status":
        print(
            json.dumps(
                {
                    "id": user.pk,
                    "nickname": user.nickname,
                    "email_verified": has_verified_primary_email(user),
                    "profile_complete": profile_complete(user),
                    "has_usable_password": user.has_usable_password(),
                    "social_accounts": list(
                        user.socialaccount_set.order_by("provider").values_list(
                            "provider", flat=True
                        )
                    ),
                },
                sort_keys=True,
            )
        )
        return
    raise SystemExit("unsupported auth-state action")


if __name__ == "__main__":
    main()
