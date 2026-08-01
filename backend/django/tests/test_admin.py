import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.users.admin import ProjectUserCreationForm
from apps.users.models import NicknameHistory
from apps.users.wagtail_forms import (
    Stage17WagtailUserCreationForm,
    Stage17WagtailUserEditForm,
)
from tests.identity import create_identity_user


def test_custom_user_model_is_configured():
    assert settings.AUTH_USER_MODEL == "users.User"


@pytest.mark.parametrize("path", ["/django-admin/", "/cms/"])
def test_admin_routes_require_authentication(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert "login" in response.headers["Location"]


@pytest.mark.django_db
def test_model_backend_password_login_remains_available_for_admin(client):
    user = get_user_model().objects.create_superuser(
        username="owner",
        email="owner@example.com",
        password="safe-test-password",
    )

    assert client.login(username=user.username, password="safe-test-password") is True
    assert client.get("/django-admin/").status_code == 200
    assert client.get("/cms/").status_code == 200


@pytest.mark.django_db
def test_wagtail_reset_and_email_change_side_doors_are_disabled(client):
    login = client.get("/cms/login/")

    assert login.status_code == 200
    assert b"Forgotten password" not in login.content
    assert client.get("/cms/password_reset/").status_code == 404

    actor = create_identity_user(
        username="wagtail-admin",
        email="wagtail-admin@example.com",
        nickname="Wagtail Admin",
        superuser=True,
    )
    client.force_login(actor)
    account = client.get("/cms/account/")

    assert account.status_code == 200
    assert b'name="email"' not in account.content


@pytest.mark.django_db
def test_duplicate_allauth_local_html_login_and_signup_are_disabled(client):
    user_count = get_user_model().objects.count()
    login = client.post(
        "/accounts/login/",
        {"login": "reader@example.com", "password": "not-used"},
    )
    signup = client.post(
        "/accounts/signup/",
        {"email": "reader@example.com", "password1": "not-used"},
    )

    assert login.status_code == 404
    assert signup.status_code == 404
    assert "_auth_user_id" not in client.session
    assert get_user_model().objects.count() == user_count


@pytest.mark.parametrize(
    "path",
    [
        "/accounts/email/",
        "/accounts/password/change/",
        "/accounts/password/reset/confirm/",
        "/accounts/login/code/",
        "/accounts/signup/passkey/",
        "/accounts/google/login/token/",
        "/accounts/3rdparty/",
        "/accounts/3rdparty/signup/",
        "/accounts/social/connections/",
        "/accounts/2fa/",
        "/accounts/sessions/",
    ],
)
@pytest.mark.django_db
def test_duplicate_allauth_account_management_surfaces_are_disabled(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.django_db
def test_allauth_identity_admin_is_read_only_and_social_tokens_are_unregistered(client):
    actor = create_identity_user(
        username="identity-admin",
        email="identity-admin@example.com",
        nickname="Identity Admin",
        superuser=True,
    )
    target = create_identity_user(
        username="identity-target",
        email="identity-target@example.com",
        nickname="Identity Target",
    )
    other = create_identity_user(
        username="identity-other",
        email="identity-other@example.com",
        nickname="Identity Other",
    )
    account = SocialAccount.objects.create(
        user=target,
        provider="github",
        uid="flow-owned-social-identity",
    )
    address = EmailAddress.objects.get(user=target)
    client.force_login(actor)

    email_change = client.post(
        f"/django-admin/account/emailaddress/{address.pk}/change/",
        {
            "user": other.pk,
            "email": "captured@example.com",
            "primary": "on",
            "verified": "on",
        },
    )
    social_change = client.post(
        f"/django-admin/socialaccount/socialaccount/{account.pk}/change/",
        {
            "user": other.pk,
            "provider": "github",
            "uid": account.uid,
            "extra_data": "{}",
        },
    )

    address.refresh_from_db()
    account.refresh_from_db()
    assert email_change.status_code == social_change.status_code == 403
    assert address.user_id == account.user_id == target.pk
    assert address.email == target.email_normalized
    assert client.get("/django-admin/socialaccount/socialtoken/").status_code == 404
    assert SocialToken.objects.count() == 0


@pytest.mark.django_db
def test_admin_created_user_gets_canonical_email_confirmed_nickname_and_audit():
    actor = create_identity_user(
        username="admin-actor",
        email="admin-actor@example.com",
        nickname="Admin Actor",
        password="Stage17!admin-actor-password",
        superuser=True,
    )
    form = ProjectUserCreationForm(
        data={
            "username": "internal-new-user",
            "email": "New.User@Example.com",
            "nickname": "Support",
            "password1": "Stage17!violet-circuit-582",
            "password2": "Stage17!violet-circuit-582",
        }
    )
    assert form.is_valid(), form.errors
    user = form.save(commit=False)
    request = RequestFactory().post("/django-admin/users/user/add/")
    request.user = actor

    admin.site._registry[get_user_model()].save_model(request, user, form, change=False)

    user.refresh_from_db()
    audit = NicknameHistory.objects.get(user=user)
    assert user.email == user.email_normalized == "new.user@example.com"
    assert user.nickname == "Support"
    assert user.nickname_confirmed is True
    assert audit.change_kind == NicknameHistory.ChangeKind.STAFF_OVERRIDE
    assert audit.actor_id == actor.pk
    assert audit.reason == "Account created through Django Admin"


@pytest.mark.django_db
def test_existing_admin_user_email_is_read_only_outside_email_change_scope():
    user = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
    )
    request = RequestFactory().get(f"/django-admin/users/user/{user.pk}/change/")
    request.user = create_identity_user(
        username="admin-actor",
        email="admin@example.com",
        nickname="Admin Person",
        superuser=True,
    )

    readonly = admin.site._registry[get_user_model()].get_readonly_fields(
        request,
        obj=user,
    )

    assert "email" in readonly


@pytest.mark.django_db
def test_wagtail_created_user_gets_canonical_identity_and_history():
    form = Stage17WagtailUserCreationForm(
        data={
            "username": "internal-wagtail-user",
            "email": "Wagtail.User@Example.com",
            "nickname": "Wagtail Reader",
            "first_name": "Legacy",
            "last_name": "Name",
            "password1": "Stage17!wagtail-violet-582",
            "password2": "Stage17!wagtail-violet-582",
        }
    )

    assert form.is_valid(), form.errors
    user = form.save()
    history = NicknameHistory.objects.get(user=user)

    assert user.email == user.email_normalized == "wagtail.user@example.com"
    assert user.nickname == "Wagtail Reader"
    assert user.nickname_confirmed is True
    assert history.nickname_normalized == "wagtail reader"
    assert history.change_kind == NicknameHistory.ChangeKind.INITIAL
    assert history.reason == "Account created through Wagtail Admin"


@pytest.mark.django_db
def test_wagtail_user_edit_cannot_change_email_or_nickname():
    user = create_identity_user(
        username="internal-reader",
        email="reader@example.com",
        nickname="Public Reader",
    )
    form = Stage17WagtailUserEditForm(
        instance=user,
        data={
            "username": user.username,
            "email": "attacker@example.com",
            "nickname": "Hijacked Name",
            "first_name": "Updated",
            "last_name": "Name",
            "is_active": True,
            "password1": "",
            "password2": "",
        },
    )

    assert form.is_valid(), form.errors
    form.save()
    user.refresh_from_db()

    assert user.email == user.email_normalized == "reader@example.com"
    assert user.nickname == "Public Reader"
    assert user.nickname_history.count() == 1


@pytest.mark.django_db
def test_wagtail_user_listing_uses_nickname_and_hides_internal_username(client):
    actor = create_identity_user(
        username="wagtail-admin",
        email="wagtail-admin@example.com",
        nickname="Wagtail Admin",
        superuser=True,
    )
    create_identity_user(
        username="opaque-internal-identity",
        email="moderator@example.com",
        nickname="Public Moderator",
        first_name="Legacy",
        last_name="Fullname",
    )
    client.force_login(actor)

    response = client.get("/cms/users/")

    assert response.status_code == 200
    assert b"Public Moderator" in response.content
    assert b"opaque-internal-identity" not in response.content
    assert b"Legacy Fullname" not in response.content


@pytest.mark.django_db
def test_wagtail_builtin_display_helpers_use_authoritative_nickname():
    from wagtail.admin.utils import get_user_display_name

    user = create_identity_user(
        username="opaque-internal-user",
        email="author@example.com",
        nickname="Visible Author",
        first_name="Legacy",
        last_name="Fullname",
    )

    assert user.get_full_name() == "Visible Author"
    assert user.get_short_name() == "Visible Author"
    assert get_user_display_name(user) == "Visible Author"
