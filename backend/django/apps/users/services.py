from __future__ import annotations

from datetime import timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.users.identity import normalize_email_address, normalize_nickname
from apps.users.models import AuthCredential, NicknameHistory, User

NICKNAME_CHANGE_COOLDOWN = timedelta(days=30)


class IdentityInvariantError(RuntimeError):
    pass


def public_display_name(user: User) -> str:
    """Return the only public author name accepted after Stage 17 activation."""

    if not user.nickname or not user.nickname_normalized:
        raise IdentityInvariantError(f"User {user.pk} has no authoritative nickname")
    return user.nickname


def is_site_author(user: User) -> bool:
    return bool(user.is_site_author)


def primary_email_address(user: User):
    if not user.is_authenticated:
        return None
    if hasattr(user, "_stage17_primary_email_address"):
        return user._stage17_primary_email_address
    address = EmailAddress.objects.filter(user=user, primary=True).order_by("pk").first()
    user._stage17_primary_email_address = address
    return address


def has_verified_primary_email(user: User) -> bool:
    address = primary_email_address(user)
    if not address or not address.verified:
        return False
    try:
        _, key = normalize_email_address(address.email)
    except ValidationError:
        return False
    return bool(user.email_normalized and key == user.email_normalized)


def profile_complete(user: User) -> bool:
    return bool(user.nickname_confirmed and user.nickname and user.nickname_normalized)


def can_interact(user: User) -> bool:
    return bool(
        user.is_authenticated
        and user.is_active
        and not user.is_banned
        and profile_complete(user)
        and has_verified_primary_email(user)
    )


def ensure_can_interact(user: User) -> None:
    if not user.is_authenticated:
        raise PermissionDenied("Authentication is required.")
    if not user.is_active or user.is_banned:
        raise PermissionDenied("This account is unavailable.")
    if not profile_complete(user):
        raise PermissionDenied("Profile completion is required.")
    if not has_verified_primary_email(user):
        raise PermissionDenied("Email verification is required.")


def nickname_change_available_at(user: User):
    if not user.nickname_confirmed or user.nickname_changed_at is None:
        return None
    return user.nickname_changed_at + NICKNAME_CHANGE_COOLDOWN


def _site_owner_id_and_nickname() -> tuple[int | None, str | None]:
    marked = list(User.objects.filter(is_site_author=True).values_list("pk", "nickname")[:2])
    if len(marked) == 1:
        return marked[0]
    if len(marked) > 1:
        return None, None
    try:
        _, owner_key = normalize_email_address(settings.SITE_OWNER_EMAIL)
    except ValidationError:
        owner_key = None
    owners = (
        list(User.objects.filter(email_normalized=owner_key).values_list("pk", "nickname")[:2])
        if owner_key
        else []
    )
    if not owners:
        # A unique superuser is an internal compatibility proof for installs
        # that promoted the site owner before SITE_OWNER_EMAIL was persisted.
        # Multiple superusers remain deliberately ambiguous.
        owners = list(User.objects.filter(is_superuser=True).values_list("pk", "nickname")[:2])
    if len(owners) != 1:
        return None, None
    return owners[0]


def normalize_public_nickname(
    value: str,
    *,
    user: User | None = None,
    staff_override: bool = False,
):
    owner_id, owner_nickname = _site_owner_id_and_nickname()
    # Preserving a reserved legacy name is migration-only. At runtime even a
    # staff account must use the audited Admin override path; public profile
    # mutations never inherit privileges from is_staff/is_superuser.
    allow_reserved = bool(staff_override)
    reserved_values = (
        (owner_nickname,) if owner_nickname and (user is None or user.pk != owner_id) else ()
    )
    return normalize_nickname(
        value,
        reserved_values=reserved_values,
        allow_reserved=allow_reserved,
    )


@transaction.atomic
def claim_initial_nickname(*, user: User, nickname: str, confirmed: bool) -> User:
    locked = User.objects.select_for_update().get(pk=user.pk)
    if locked.nickname_normalized or NicknameHistory.objects.filter(user=locked).exists():
        raise ValidationError({"nickname": "An initial nickname has already been claimed."})
    normalized = normalize_public_nickname(nickname, user=locked)
    try:
        with transaction.atomic():
            NicknameHistory.objects.create(
                user=locked,
                nickname=normalized.display,
                nickname_normalized=normalized.key,
                change_kind=NicknameHistory.ChangeKind.INITIAL,
            )
            locked.nickname = normalized.display
            locked.nickname_normalized = normalized.key
            locked.nickname_confirmed = confirmed
            locked.nickname_changed_at = None
            locked.save(
                update_fields=(
                    "nickname",
                    "nickname_normalized",
                    "nickname_confirmed",
                    "nickname_changed_at",
                )
            )
    except IntegrityError:
        raise ValidationError({"nickname": "This nickname is unavailable."}) from None
    return locked


@transaction.atomic
def change_nickname(
    *,
    user: User,
    nickname: str,
    actor: User | None = None,
    staff_override: bool = False,
    reason: str = "",
    at=None,
) -> User:
    now = at or timezone.now()
    locked = User.objects.select_for_update().get(pk=user.pk)
    # Staff may override the cooldown and reserved-name policy with a recorded
    # reason, but an unavailable account is never mutable through this service.
    if not locked.is_active or locked.is_banned:
        raise PermissionDenied("This account is unavailable.")
    if staff_override:
        if actor is None or not actor.is_active or not actor.is_staff:
            raise PermissionDenied("An active staff actor is required.")
        reason = reason.strip()
        if not reason:
            raise ValidationError({"nickname_override_reason": "An audit reason is required."})

    normalized = normalize_public_nickname(
        nickname,
        user=locked,
        staff_override=staff_override,
    )
    if normalized.key == locked.nickname_normalized:
        if normalized.display != locked.nickname:
            raise ValidationError(
                {"nickname": "Capitalization-only nickname changes are not supported."}
            )
        if not locked.nickname_confirmed:
            # Expansion/backfill and new OAuth users already own a permanent
            # history claim for their proposed nickname. Explicitly accepting
            # that exact value completes the profile without creating a
            # duplicate claim or starting the rename cooldown.
            locked.nickname_confirmed = True
            locked.nickname_changed_at = None
            locked.save(update_fields=("nickname_confirmed", "nickname_changed_at"))
        return locked

    initial_completion = not locked.nickname_confirmed
    available_at = nickname_change_available_at(locked)
    if not staff_override and not initial_completion and available_at and now < available_at:
        raise ValidationError(
            {
                "nickname": "Nickname changes are limited to once every 30 days.",
                "nickname_change_available_at": available_at.isoformat(),
            }
        )

    change_kind = (
        NicknameHistory.ChangeKind.STAFF_OVERRIDE
        if staff_override
        else NicknameHistory.ChangeKind.INITIAL
        if initial_completion
        else NicknameHistory.ChangeKind.CHANGE
    )
    try:
        with transaction.atomic():
            NicknameHistory.objects.create(
                user=locked,
                nickname=normalized.display,
                nickname_normalized=normalized.key,
                change_kind=change_kind,
                actor=actor if staff_override else None,
                reason=reason if staff_override else "",
            )
            locked.nickname = normalized.display
            locked.nickname_normalized = normalized.key
            locked.nickname_confirmed = True
            locked.nickname_changed_at = None if initial_completion else now
            locked.save(
                update_fields=(
                    "nickname",
                    "nickname_normalized",
                    "nickname_confirmed",
                    "nickname_changed_at",
                )
            )
    except IntegrityError:
        raise ValidationError({"nickname": "This nickname is unavailable."}) from None

    from apps.blog.models import BlogPostPage
    from apps.blog.services.revalidation import (
        create_revalidation_event,
        deliver_event_after_commit,
    )

    # Draft previews bypass the public Next cache and must never be represented
    # as a publish event merely because their author's nickname changed.
    for page in BlogPostPage.objects.filter(owner=locked, live=True).only("pk", "slug"):
        event = create_revalidation_event(page)
        deliver_event_after_commit(event.pk)
    return locked


@transaction.atomic
def advance_auth_state(user: User, *, revoke_credentials: bool = True) -> User:
    locked = User.objects.select_for_update().get(pk=user.pk)
    User.objects.filter(pk=locked.pk).update(auth_state_version=F("auth_state_version") + 1)
    locked.refresh_from_db(fields=("auth_state_version",))
    if revoke_credentials:
        AuthCredential.objects.filter(
            user=locked,
            used_at__isnull=True,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
    return locked


@transaction.atomic
def set_account_availability(*, user: User, active: bool | None = None, banned=None):
    locked = User.objects.select_for_update().get(pk=user.pk)
    changed_fields = []
    if active is not None and locked.is_active != active:
        locked.is_active = active
        changed_fields.append("is_active")
    if banned is not None and locked.is_banned != banned:
        locked.is_banned = banned
        changed_fields.append("is_banned")
    if changed_fields:
        locked.auth_state_version += 1
        changed_fields.append("auth_state_version")
        locked.save(update_fields=changed_fields)
        AuthCredential.objects.filter(
            user=locked,
            used_at__isnull=True,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
    return locked


def normalize_user_email(user: User, value: str) -> str:
    _, canonical = normalize_email_address(value)
    user.email = canonical
    user.email_normalized = canonical
    return canonical
