from io import StringIO

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

pytestmark = pytest.mark.django_db


def test_owner_command_requires_configured_valid_existing_user(settings):
    settings.SITE_OWNER_EMAIL = ""
    with pytest.raises(CommandError, match="not configured"):
        call_command("promote_site_owner")

    settings.SITE_OWNER_EMAIL = "not-an-email"
    with pytest.raises(CommandError, match="not a valid"):
        call_command("promote_site_owner")

    settings.SITE_OWNER_EMAIL = "missing@example.com"
    with pytest.raises(CommandError, match="No existing user"):
        call_command("promote_site_owner")


def test_owner_command_requires_verified_social_signup(settings):
    user = get_user_model().objects.create_user(username="owner", email="owner@example.com")
    settings.SITE_OWNER_EMAIL = user.email
    SocialAccount.objects.create(user=user, provider="google", uid="owner-google")
    EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)

    with pytest.raises(CommandError, match="verified Google or GitHub"):
        call_command("promote_site_owner")

    user.refresh_from_db()
    assert user.is_staff is False
    assert user.is_superuser is False


def test_owner_command_is_idempotent_and_does_not_promote_other_users(settings):
    owner = get_user_model().objects.create_user(username="owner", email="owner@example.com")
    other = get_user_model().objects.create_user(username="reader", email="reader@example.com")
    EmailAddress.objects.create(user=owner, email=owner.email, verified=True, primary=True)
    SocialAccount.objects.create(user=owner, provider="github", uid="owner-github")
    settings.SITE_OWNER_EMAIL = "OWNER@example.com"

    first = StringIO()
    second = StringIO()
    call_command("promote_site_owner", stdout=first)
    call_command("promote_site_owner", stdout=second)

    owner.refresh_from_db()
    other.refresh_from_db()
    assert owner.is_staff is True
    assert owner.is_superuser is True
    assert other.is_staff is False
    assert other.is_superuser is False
    assert "permissions granted" in first.getvalue()
    assert "already has" in second.getvalue()
