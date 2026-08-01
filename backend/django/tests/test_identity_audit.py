import json
from datetime import timedelta
from io import StringIO

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.users.models import NicknameHistory, User
from tests.identity import create_identity_user

pytestmark = pytest.mark.django_db


def test_stage17_identity_audit_is_bounded_and_does_not_emit_email_values():
    create_identity_user(
        username="owner",
        email="owner@example.com",
        nickname="Site Owner",
        superuser=True,
        site_author=True,
    )
    create_identity_user(
        username="reader",
        email="private-reader@example.com",
        nickname="Private Reader",
        verified=False,
    )
    output = StringIO()

    call_command("audit_stage17_identity", stdout=output)

    raw = output.getvalue()
    report = json.loads(raw)
    assert report["schema"] == "stage17-identity-audit/v2"
    assert report["users"]["total"] == 2
    assert report["users"]["verified_primary"] == 1
    assert report["users"]["unverified_or_missing_primary"] == 1
    assert report["audit"]["duplicate_email_key_count"] == 0
    assert report["audit"]["duplicate_email_user_ids"] == []
    assert report["audit"]["invalid_email_address_ids"] == []
    assert report["audit"]["duplicate_email_address_ids"] == []
    assert report["audit"]["duplicate_email_address_user_ids"] == []
    assert report["audit"]["mismatched_primary_email_address_user_ids"] == []
    assert report["audit"]["invalid_verified_email_address_ids"] == []
    assert report["audit"]["duplicate_verified_email_address_ids"] == []
    assert report["audit"]["duplicate_verified_email_address_user_ids"] == []
    assert report["audit"]["missing_nickname_claim_user_ids"] == []
    assert "owner@example.com" not in raw
    assert "private-reader@example.com" not in raw


def test_activation_ready_audit_rejects_missing_claims_and_social_tokens():
    owner = create_identity_user(
        username="owner",
        email="owner@example.com",
        nickname="Site Owner",
        superuser=True,
        site_author=True,
    )
    owner.nickname_history.all().delete()
    account = SocialAccount.objects.create(user=owner, provider="github", uid="audit-token")
    SocialToken.objects.create(account=account, token="must-not-persist")
    output = StringIO()

    with pytest.raises(CommandError, match="not activation-ready"):
        call_command(
            "audit_stage17_identity",
            require_activation_ready=True,
            stdout=output,
        )

    report = json.loads(output.getvalue())
    assert report["audit"]["missing_nickname_claim_user_ids"] == [owner.pk]
    assert report["preserved_relations"]["social_tokens"] == 1
    assert "must-not-persist" not in output.getvalue()


def test_activation_ready_audit_rejects_canonical_verified_address_collisions():
    owner = create_identity_user(
        username="owner",
        email="kirill@example.com",
        nickname="Site Owner",
        superuser=True,
        site_author=True,
    )
    other = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
    )
    duplicate = EmailAddress.objects.create(
        user=other,
        email="Kirill@example.com",
        primary=False,
        verified=True,
    )
    output = StringIO()

    with pytest.raises(CommandError, match="not activation-ready"):
        call_command(
            "audit_stage17_identity",
            require_activation_ready=True,
            stdout=output,
        )

    report = json.loads(output.getvalue())
    assert report["audit"]["invalid_verified_email_address_ids"] == []
    assert report["audit"]["duplicate_email_address_ids"] == sorted(
        [EmailAddress.objects.get(user=owner).pk, duplicate.pk]
    )
    assert report["audit"]["duplicate_email_address_user_ids"] == sorted([owner.pk, other.pk])
    assert report["audit"]["duplicate_verified_email_address_ids"] == sorted(
        [EmailAddress.objects.get(user=owner).pk, duplicate.pk]
    )
    assert report["audit"]["duplicate_verified_email_address_user_ids"] == sorted(
        [owner.pk, other.pk]
    )
    assert duplicate.email not in output.getvalue()


def test_activation_ready_audit_rejects_unverified_canonical_address_ambiguity():
    owner = create_identity_user(
        username="owner",
        email="kirill@example.com",
        nickname="Site Owner",
        superuser=True,
        site_author=True,
    )
    other = create_identity_user(
        username="reader",
        email="reader@example.com",
        nickname="Reader",
        verified=False,
    )
    duplicate = EmailAddress.objects.create(
        user=other,
        email="Kirill@example.com",
        primary=False,
        verified=False,
    )
    output = StringIO()

    with pytest.raises(CommandError, match="not activation-ready"):
        call_command(
            "audit_stage17_identity",
            require_activation_ready=True,
            stdout=output,
        )

    report = json.loads(output.getvalue())
    owner_address = EmailAddress.objects.get(user=owner)
    assert report["audit"]["duplicate_email_address_ids"] == sorted(
        [owner_address.pk, duplicate.pk]
    )
    assert report["audit"]["duplicate_email_address_user_ids"] == sorted([owner.pk, other.pk])
    assert report["audit"]["duplicate_verified_email_address_ids"] == []
    assert duplicate.email not in output.getvalue()


@pytest.mark.django_db(transaction=True)
def test_runtime_catchup_repairs_a_user_created_by_the_rollback_digest():
    create_identity_user(
        username="owner",
        email="owner@example.com",
        nickname="Site Owner",
        superuser=True,
        site_author=True,
    )
    executor = MigrationExecutor(connection)
    stage16_apps = executor.loader.project_state([("users", "0001_initial")]).apps
    Stage16User = stage16_apps.get_model("users", "User")
    legacy = Stage16User.objects.create_user(
        username="rollback-reader",
        email="Rollback.Reader@Example.com",
    )
    EmailAddress.objects.create(
        user_id=legacy.pk,
        email="rollback.reader@example.com",
        primary=True,
        verified=True,
    )
    SocialAccount.objects.create(user_id=legacy.pk, provider="github", uid="rollback-oauth")
    session = Session.objects.create(
        session_key="stage17rollbackcatchupsession",
        session_data="preserved-rollback-session",
        expire_date=timezone.now() + timedelta(days=1),
    )

    first = StringIO()
    second = StringIO()
    call_command("catchup_stage17_identity", stdout=first)
    call_command("catchup_stage17_identity", stdout=second)

    repaired = User.objects.get(pk=legacy.pk)
    assert repaired.email == repaired.email_normalized == "rollback.reader@example.com"
    assert repaired.nickname == "rollback-reader"
    assert repaired.nickname_normalized == "rollback-reader"
    assert repaired.nickname_confirmed is False
    assert NicknameHistory.objects.filter(user=repaired).count() == 1
    assert SocialAccount.objects.get(uid="rollback-oauth").user_id == repaired.pk
    assert Session.objects.get(pk=session.pk).session_data == "preserved-rollback-session"
    assert "stage17_identity_catchup=complete" in first.getvalue()
    assert "stage17_identity_catchup=complete" in second.getvalue()

    call_command("audit_stage17_identity", require_activation_ready=True, stdout=StringIO())
