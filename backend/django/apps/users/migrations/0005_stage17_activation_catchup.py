import re
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import migrations, models

if unicodedata.unidata_version != "15.0.0":
    raise RuntimeError(
        "Stage 17 activation requires Python Unicode data 15.0.0, "
        f"got {unicodedata.unidata_version}"
    )

PUNCTUATION = frozenset("-_.\u00b7'\u2019")
RESERVED = frozenset({"admin", "administrator", "moderator", "staff", "system", "support"})
CONFUSABLE_TO_ASCII = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "х": "x",
        "у": "y",
        "ѕ": "s",
        "і": "i",
        "ј": "j",
        "һ": "h",
        "к": "k",
        "ӏ": "l",
        "ԁ": "d",
        "α": "a",
        "ε": "e",
        "ι": "i",
        "κ": "k",
        "ο": "o",
        "ρ": "p",
        "τ": "t",
        "υ": "y",
        "χ": "x",
    }
)
DEFAULT_IGNORABLE_RANGES = (
    (0x034F, 0x034F),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFFA0, 0xFFA0),
    (0xE0000, 0xE0FFF),
)
SYNTHETIC = re.compile(
    r"^(?:usr_[0-9a-f]{24,}|user[-_]?\d+|(?:google|github)[-_].+)$",
    re.IGNORECASE,
)


def _email_key(value):
    if not isinstance(value, str):
        return None
    source = value.strip()
    if not source or len(source) > 254 or source.count("@") != 1:
        return None
    try:
        source.encode("utf-8")
        validate_email(source)
        local, domain = source.rsplit("@", 1)
        domain = domain.encode("idna").decode("ascii").lower()
        key = f"{unicodedata.normalize('NFKC', local).casefold()}@{domain}"
        key.encode("utf-8")
        validate_email(key)
    except (UnicodeError, ValidationError):
        return None
    return key if len(key) <= 254 else None


def _noncharacter(value):
    return 0xFDD0 <= value <= 0xFDEF or value & 0xFFFF in {0xFFFE, 0xFFFF}


def _default_ignorable(value):
    return any(start <= value <= end for start, end in DEFAULT_IGNORABLE_RANGES)


def _skeleton(value):
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        .casefold()
        .translate(CONFUSABLE_TO_ASCII)
        if not unicodedata.category(character).startswith("M")
        and (character.isalnum() or character in PUNCTUATION or character == " ")
    ).translate(str.maketrans("", "", "-_.\u00b7'\u2019 "))


def _nickname(value, *, allow_reserved=False, reserved_values=()):
    if not isinstance(value, str):
        return None
    pieces = []
    pending = False
    for character in value:
        category = unicodedata.category(character)
        if (
            category.startswith("C")
            or category in {"Zl", "Zp"}
            or _noncharacter(ord(character))
            or _default_ignorable(ord(character))
        ):
            return None
        if category == "Zs":
            pending = bool(pieces)
            continue
        if pending:
            pieces.append(" ")
            pending = False
        pieces.append(character)
    display = unicodedata.normalize("NFC", "".join(pieces).strip())
    try:
        encoded = display.encode("utf-8")
    except UnicodeError:
        return None
    if not 2 <= len(display) <= 40 or len(encoded) > 160:
        return None
    previous_separator = False
    has_base = False
    for index, character in enumerate(display):
        category = unicodedata.category(character)
        base = category[0] in {"L", "N"}
        mark = category[0] == "M"
        separator = character == " " or character in PUNCTUATION
        if not (base or mark or separator) or (index == 0 and not base):
            return None
        if mark and not has_base:
            return None
        if separator and previous_separator:
            return None
        previous_separator = separator
        if separator:
            has_base = False
        elif base:
            has_base = True
    if previous_separator:
        return None
    key = unicodedata.normalize("NFKC", display).casefold()
    if not allow_reserved:
        reserved_skeletons = set(RESERVED)
        for item in reserved_values:
            normalized = _nickname(item, allow_reserved=True)
            if normalized:
                reserved_skeletons.add(_skeleton(normalized[1]))
        if _skeleton(key) in reserved_skeletons:
            return None
    return display, key


def _suffix(base, user_id, used, *, allow_reserved, reserved_values=()):
    suffix = f"-{user_id}"
    trimmed = base
    while trimmed and (len(trimmed) + len(suffix) > 40 or len(f"{trimmed}{suffix}".encode()) > 160):
        trimmed = trimmed[:-1]
    trimmed = trimmed.rstrip(" -_.\u00b7'\u2019")
    for raw in (f"{trimmed}{suffix}", f"user-{user_id}"):
        candidate = _nickname(
            raw,
            allow_reserved=allow_reserved,
            reserved_values=reserved_values,
        )
        if candidate and candidate[1] not in used:
            return candidate
    for attempt in range(2, 101):
        candidate = _nickname(
            f"user-{user_id}-{attempt}",
            allow_reserved=allow_reserved,
            reserved_values=reserved_values,
        )
        if candidate and candidate[1] not in used:
            return candidate
    raise RuntimeError(f"Stage 17 could not allocate a catch-up nickname for user {user_id}")


def _candidate(user, used, *, owner_id, owner_nickname):
    allow_reserved = bool(user.is_staff or user.is_superuser or user.pk == owner_id)
    reserved_values = (owner_nickname,) if owner_nickname and user.pk != owner_id else ()
    full_name = " ".join(part for part in (user.first_name.strip(), user.last_name.strip()) if part)
    local = user.email.rsplit("@", 1)[0] if "@" in user.email else ""
    candidates = [full_name]
    if user.username and "@" not in user.username and not SYNTHETIC.fullmatch(user.username):
        candidates.append(user.username)
    candidates.extend((local, f"user-{user.pk}"))
    for raw in candidates:
        normalized = _nickname(
            raw,
            allow_reserved=allow_reserved,
            reserved_values=reserved_values,
        )
        if normalized and normalized[1] not in used:
            return normalized
        if normalized:
            return _suffix(
                normalized[0],
                user.pk,
                used,
                allow_reserved=allow_reserved,
                reserved_values=reserved_values,
            )
        # The site owner's public nickname is an impersonation boundary, but a
        # legacy user with the same otherwise-valid candidate must still follow
        # the documented deterministic collision rule instead of silently
        # falling through to a different source field.
        unrestricted = _nickname(raw, allow_reserved=True)
        owner_skeletons = {
            _skeleton(owner[1])
            for value in reserved_values
            if (owner := _nickname(value, allow_reserved=True)) is not None
        }
        if unrestricted and _skeleton(unrestricted[1]) in owner_skeletons:
            return _suffix(
                unrestricted[0],
                user.pk,
                used,
                allow_reserved=allow_reserved,
                reserved_values=reserved_values,
            )
    return _suffix(
        "user",
        user.pk,
        used,
        allow_reserved=allow_reserved,
        reserved_values=reserved_values,
    )


def _site_author_and_backfill_owner(User, BlogPostPage):
    existing_owner_ids = list(
        BlogPostPage.objects.exclude(owner_id__isnull=True)
        .order_by()
        .values_list("owner_id", flat=True)
        .distinct()[:2]
    )
    marked_ids = list(
        User.objects.filter(is_site_author=True).order_by("pk").values_list("pk", flat=True)[:2]
    )
    if len(marked_ids) == 1:
        backfill_owner_id = (
            marked_ids[0] if not existing_owner_ids or existing_owner_ids == marked_ids else None
        )
        return (
            marked_ids[0],
            backfill_owner_id,
            (
                "existing_site_author_and_unique_post_owner"
                if backfill_owner_id is not None
                else "existing_site_author_with_ambiguous_owner_backfill"
            ),
        )
    if len(marked_ids) > 1:
        return None, None, "multiple_existing_site_authors"
    owner_key = _email_key(getattr(settings, "SITE_OWNER_EMAIL", ""))
    if owner_key:
        ids = [
            user.pk
            for user in User.objects.all().only("pk", "email", "email_normalized")
            if (user.email_normalized or _email_key(user.email)) == owner_key
        ]
        if len(ids) == 1:
            backfill_owner_id = (
                ids[0] if not existing_owner_ids or existing_owner_ids == ids else None
            )
            resolution = (
                "configured_email_and_unique_post_owner"
                if backfill_owner_id is not None
                else "configured_site_author_with_ambiguous_owner_backfill"
            )
            return ids[0], backfill_owner_id, resolution

    superuser_ids = list(
        User.objects.filter(is_superuser=True).order_by("pk").values_list("pk", flat=True)[:2]
    )
    if (
        len(existing_owner_ids) == 1
        and len(superuser_ids) == 1
        and existing_owner_ids[0] == superuser_ids[0]
    ):
        return (
            existing_owner_ids[0],
            existing_owner_ids[0],
            "unique_post_owner_and_superuser",
        )
    return None, None, "ambiguous"


def forward(apps, schema_editor):
    User = apps.get_model("users", "User")
    History = apps.get_model("users", "NicknameHistory")
    Comment = apps.get_model("discussions", "Comment")
    PostReaction = apps.get_model("discussions", "PostReaction")
    CommentReaction = apps.get_model("discussions", "CommentReaction")
    BlogPostPage = apps.get_model("blog", "BlogPostPage")
    EmailAddress = apps.get_model("account", "EmailAddress")
    Page = apps.get_model("wagtailcore", "Page")
    SocialToken = apps.get_model("socialaccount", "SocialToken")

    site_author_id, backfill_owner_id, owner_resolution = _site_author_and_backfill_owner(
        User, BlogPostPage
    )
    if site_author_id is not None:
        User.objects.filter(pk=site_author_id).update(is_site_author=True)
    public_user_ids = set(Comment.objects.values_list("author_id", flat=True))
    public_user_ids.update(PostReaction.objects.values_list("user_id", flat=True))
    public_user_ids.update(CommentReaction.objects.values_list("user_id", flat=True))
    used_nicknames = set(History.objects.values_list("nickname_normalized", flat=True))
    used_nicknames.update(
        User.objects.exclude(nickname_normalized__isnull=True).values_list(
            "nickname_normalized", flat=True
        )
    )
    used_emails = {
        key: user_id
        for key, user_id in User.objects.exclude(email_normalized__isnull=True).values_list(
            "email_normalized", "pk"
        )
    }
    catchup = sorted(
        User.objects.filter(nickname_normalized__isnull=True).order_by("pk"),
        key=lambda user: (user.pk != site_author_id, user.pk),
    )
    site_author_nickname = (
        User.objects.filter(pk=site_author_id).values_list("nickname", flat=True).first()
        if site_author_id is not None
        else None
    )
    email_conflicts = []
    for user in catchup:
        email_key = _email_key(user.email)
        if not email_key:
            raise RuntimeError(f"Stage 17 user {user.pk} has no valid canonical email")
        owner = used_emails.get(email_key)
        if owner is not None and owner != user.pk:
            email_conflicts.append((owner, user.pk))
            continue
        used_emails[email_key] = user.pk
        nickname = _candidate(
            user,
            used_nicknames,
            owner_id=site_author_id,
            owner_nickname=site_author_nickname,
        )
        used_nicknames.add(nickname[1])
        confirmed = bool(
            user.is_staff
            or user.is_superuser
            or user.pk == site_author_id
            or user.pk in public_user_ids
        )
        User.objects.filter(pk=user.pk).update(
            email=email_key,
            email_normalized=email_key,
            nickname=nickname[0],
            nickname_normalized=nickname[1],
            nickname_confirmed=confirmed,
            nickname_changed_at=None,
        )
        History.objects.create(
            user_id=user.pk,
            nickname=nickname[0],
            nickname_normalized=nickname[1],
            change_kind="backfill",
            reason="Stage 17 activation catch-up",
        )
        if user.pk == site_author_id:
            site_author_nickname = nickname[0]

    public_posts = BlogPostPage.objects.filter(live=True, first_published_at__isnull=False)
    all_ownerless = list(
        BlogPostPage.objects.filter(owner_id__isnull=True).values_list("pk", flat=True)
    )
    owner_backfilled = 0
    if all_ownerless and backfill_owner_id is not None:
        # Preview responses use the same authoritative author contract. Repair
        # drafts as well as public pages, but only after the same proof used for
        # public ownership has resolved one site owner.
        owner_backfilled = Page.objects.filter(
            pk__in=all_ownerless,
            owner_id__isnull=True,
        ).update(owner_id=backfill_owner_id)
    unresolved_public = list(
        public_posts.filter(owner_id__isnull=True).values_list("pk", flat=True)
    )
    unresolved_all = list(
        BlogPostPage.objects.filter(owner_id__isnull=True).values_list("pk", flat=True)
    )
    invalid_email_ids = []
    mismatched_email_ids = []
    canonical_email_owners = {}
    canonical_email_conflicts = []
    canonical_email_by_user = {}
    invalid_nickname_ids = []
    for user in User.objects.order_by("pk"):
        email_key = _email_key(user.email)
        if email_key is None:
            invalid_email_ids.append(user.pk)
        else:
            existing_owner = canonical_email_owners.get(email_key)
            if existing_owner is not None and existing_owner != user.pk:
                canonical_email_conflicts.append((existing_owner, user.pk))
            else:
                canonical_email_owners[email_key] = user.pk
            if user.email_normalized != email_key:
                mismatched_email_ids.append(user.pk)
            canonical_email_by_user[user.pk] = email_key

        legacy_privileged = bool(user.is_staff or user.is_superuser or user.pk == site_author_id)
        nickname = _nickname(
            user.nickname,
            allow_reserved=legacy_privileged,
            reserved_values=(site_author_nickname,) if site_author_nickname else (),
        )
        if nickname is None or nickname[1] != user.nickname_normalized:
            invalid_nickname_ids.append(user.pk)

    invalid_email_address_ids = []
    duplicate_email_address_ids = set()
    duplicate_email_address_user_ids = set()
    mismatched_primary_email_address_user_ids = set()
    canonical_address_owners = {}
    for address in EmailAddress.objects.order_by("pk"):
        address_key = _email_key(address.email)
        if address_key is None:
            invalid_email_address_ids.append(address.pk)
            if address.primary:
                mismatched_primary_email_address_user_ids.add(address.user_id)
            continue
        prior = canonical_address_owners.get(address_key)
        if prior is not None:
            prior_user_id, prior_address_id = prior
            duplicate_email_address_ids.update((prior_address_id, address.pk))
            duplicate_email_address_user_ids.update((prior_user_id, address.user_id))
        else:
            canonical_address_owners[address_key] = (address.user_id, address.pk)
        if address.primary and address_key != canonical_email_by_user.get(address.user_id):
            mismatched_primary_email_address_user_ids.add(address.user_id)

    nickname_claims = set(History.objects.values_list("user_id", "nickname_normalized"))
    missing_nickname_claim_user_ids = [
        user_id
        for user_id, nickname_key in User.objects.order_by("pk").values_list(
            "pk", "nickname_normalized"
        )
        if (user_id, nickname_key) not in nickname_claims
    ]
    social_token_count = SocialToken.objects.count()

    site_author_ids = list(
        User.objects.filter(is_site_author=True).order_by("pk").values_list("pk", flat=True)[:2]
    )
    null_users = list(
        User.objects.filter(
            models.Q(email_normalized__isnull=True)
            | models.Q(nickname__isnull=True)
            | models.Q(nickname_normalized__isnull=True)
        ).values_list("pk", flat=True)
    )
    print(
        "Stage 17 activation catch-up: "
        f"users={len(catchup)} email_conflicts={email_conflicts[:100]} "
        f"canonical_email_conflicts={canonical_email_conflicts[:100]} "
        f"invalid_email_ids={invalid_email_ids[:100]} "
        f"mismatched_email_ids={mismatched_email_ids[:100]} "
        f"invalid_email_address_ids={invalid_email_address_ids[:100]} "
        f"duplicate_email_address_ids={sorted(duplicate_email_address_ids)[:100]} "
        "duplicate_email_address_user_ids="
        f"{sorted(duplicate_email_address_user_ids)[:100]} "
        "mismatched_primary_email_address_user_ids="
        f"{sorted(mismatched_primary_email_address_user_ids)[:100]} "
        f"missing_nickname_claim_user_ids={missing_nickname_claim_user_ids[:100]} "
        f"social_token_count={social_token_count} "
        f"invalid_nickname_ids={invalid_nickname_ids[:100]} "
        f"null_users={null_users[:100]} owner_resolution={owner_resolution} "
        f"owner_backfilled={owner_backfilled} "
        f"public_owner_unresolved={unresolved_public[:100]} "
        f"all_owner_unresolved={unresolved_all[:100]} "
        f"site_author_ids={site_author_ids}"
    )
    if (
        email_conflicts
        or canonical_email_conflicts
        or invalid_email_ids
        or mismatched_email_ids
        or invalid_email_address_ids
        or duplicate_email_address_ids
        or mismatched_primary_email_address_user_ids
        or missing_nickname_claim_user_ids
        or social_token_count
        or invalid_nickname_ids
        or null_users
        or unresolved_all
        or (User.objects.exists() and len(site_author_ids) != 1)
    ):
        raise RuntimeError("Stage 17 activation invariants are not satisfied")


def reverse(apps, schema_editor):
    User = apps.get_model("users", "User")
    History = apps.get_model("users", "NicknameHistory")
    rows = list(
        History.objects.filter(
            change_kind="backfill",
            reason="Stage 17 activation catch-up",
        ).values_list("pk", "user_id", "nickname_normalized")
    )
    reversible_history_ids = []
    for history_id, user_id, nickname_key in rows:
        cleared = User.objects.filter(pk=user_id, nickname_normalized=nickname_key).update(
            email_normalized=None,
            nickname=None,
            nickname_normalized=None,
            nickname_confirmed=False,
            nickname_changed_at=None,
        )
        if cleared:
            reversible_history_ids.append(history_id)
    # If an activation-window user has since renamed, retain both their
    # current identity and the permanent claim on the catch-up nickname. This
    # makes a schema rollback safe after traffic has reached the new release.
    History.objects.filter(pk__in=reversible_history_ids).delete()


class Migration(migrations.Migration):
    dependencies = [("users", "0004_stage17_legacy_insert_defaults")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_site_author",
            field=models.BooleanField(default=False, db_default=False, editable=False),
        ),
        migrations.RunPython(forward, reverse),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        nickname__isnull=True,
                        nickname_normalized__isnull=True,
                        nickname_confirmed=False,
                    )
                    | (
                        models.Q(nickname__isnull=False, nickname_normalized__isnull=False)
                        & ~models.Q(nickname="")
                        & ~models.Q(nickname_normalized="")
                    )
                ),
                name="users_nickname_rollout_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(nickname_changed_at__isnull=True)
                | models.Q(nickname_confirmed=True),
                name="users_nickname_change_confirmed",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(email_normalized__isnull=True) | ~models.Q(email_normalized=""),
                name="users_email_key_nonempty",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                fields=("is_site_author",),
                condition=models.Q(is_site_author=True),
                name="users_single_site_author",
            ),
        ),
    ]
