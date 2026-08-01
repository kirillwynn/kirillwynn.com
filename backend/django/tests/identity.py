from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model

from apps.users.identity import normalize_email_address, normalize_nickname
from apps.users.models import NicknameHistory


def create_identity_user(
    *,
    username,
    email,
    nickname,
    password=None,
    verified=True,
    superuser=False,
    site_author=False,
    nickname_confirmed=True,
    **extra,
):
    canonical = normalize_email_address(email)[1]
    normalized = normalize_nickname(
        nickname, allow_reserved=superuser or extra.get("is_staff", False)
    )
    create = (
        get_user_model().objects.create_superuser
        if superuser
        else get_user_model().objects.create_user
    )
    user = create(
        username=username,
        email=canonical,
        password=password,
        email_normalized=canonical,
        nickname=normalized.display,
        nickname_normalized=normalized.key,
        nickname_confirmed=nickname_confirmed,
        is_site_author=site_author,
        **extra,
    )
    NicknameHistory.objects.create(
        user=user,
        nickname=normalized.display,
        nickname_normalized=normalized.key,
        change_kind=NicknameHistory.ChangeKind.INITIAL,
    )
    EmailAddress.objects.create(
        user=user,
        email=canonical,
        primary=True,
        verified=verified,
    )
    return user
