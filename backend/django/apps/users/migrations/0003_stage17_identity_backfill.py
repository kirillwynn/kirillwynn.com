import re
import unicodedata

from django.conf import settings
from django.db import migrations

MIN_NICKNAME_LENGTH = 2
MAX_NICKNAME_LENGTH = 40
MAX_NICKNAME_BYTES = 160
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
        "і": "i",
        "ј": "j",
        "һ": "h",
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
SYNTHETIC_USERNAME = re.compile(
    r"^(?:usr_[0-9a-f]{24,}|user[-_]?\d+|(?:google|github)[-_].+)$",
    re.IGNORECASE,
)


def _email_key(value):
    if not isinstance(value, str):
        return None
    source = value.strip()
    if not source or len(source) > 320 or source.count("@") != 1:
        return None
    try:
        source.encode("utf-8")
        local, domain = source.rsplit("@", 1)
        domain = domain.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None
    key = f"{unicodedata.normalize('NFKC', local).casefold()}@{domain}"
    return key if len(key) <= 320 else None


def _noncharacter(code_point):
    return 0xFDD0 <= code_point <= 0xFDEF or code_point & 0xFFFF in {0xFFFE, 0xFFFF}


def _collapse_spaces(value):
    pieces = []
    pending = False
    for character in value:
        if unicodedata.category(character) == "Zs":
            pending = bool(pieces)
        else:
            if pending:
                pieces.append(" ")
                pending = False
            pieces.append(character)
    return "".join(pieces).strip()


def _nickname(value, *, allow_reserved=False):
    if not isinstance(value, str):
        return None
    for character in value:
        category = unicodedata.category(character)
        if category.startswith("C") or category in {"Zl", "Zp"} or _noncharacter(ord(character)):
            return None
    try:
        value.encode("utf-8")
    except UnicodeError:
        return None
    display = unicodedata.normalize("NFC", _collapse_spaces(value))
    if not MIN_NICKNAME_LENGTH <= len(display) <= MAX_NICKNAME_LENGTH:
        return None
    if len(display.encode("utf-8")) > MAX_NICKNAME_BYTES:
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
        has_base = has_base or base
    if previous_separator:
        return None
    key = unicodedata.normalize("NFKC", display).casefold()
    skeleton = "".join(
        character
        for character in unicodedata.normalize("NFKD", key).translate(CONFUSABLE_TO_ASCII)
        if not unicodedata.category(character).startswith("M")
        and (character.isalnum() or character in PUNCTUATION or character == " ")
    ).translate(str.maketrans("", "", "-_.\u00b7'\u2019 "))
    if not allow_reserved and skeleton in RESERVED:
        return None
    return display, key


def _synthetic_username(value):
    return not value or "@" in value or bool(SYNTHETIC_USERNAME.fullmatch(value))


def _suffix_candidate(base, user_id, used, *, allow_reserved):
    suffix = f"-{user_id}"
    trimmed = base
    while trimmed and (
        len(trimmed) + len(suffix) > MAX_NICKNAME_LENGTH
        or len(f"{trimmed}{suffix}".encode()) > MAX_NICKNAME_BYTES
    ):
        trimmed = trimmed[:-1]
    trimmed = trimmed.rstrip(" -_.\u00b7'\u2019")
    candidate = _nickname(f"{trimmed}{suffix}", allow_reserved=allow_reserved)
    if candidate and candidate[1] not in used:
        return candidate
    fallback = _nickname(f"user-{user_id}", allow_reserved=True)
    if fallback and fallback[1] not in used:
        return fallback
    attempt = 2
    while attempt <= 100:
        fallback = _nickname(f"user-{user_id}-{attempt}", allow_reserved=True)
        if fallback and fallback[1] not in used:
            return fallback
        attempt += 1
    raise RuntimeError(f"Stage 17 could not allocate a bounded nickname for user {user_id}")


def _candidate_for(user, used, *, site_owner_id):
    allow_reserved = bool(user.is_staff or user.is_superuser or user.pk == site_owner_id)
    full_name = " ".join(part for part in (user.first_name.strip(), user.last_name.strip()) if part)
    local_part = user.email.rsplit("@", 1)[0] if "@" in user.email else ""
    raw_candidates = [full_name]
    if not _synthetic_username(user.username):
        raw_candidates.append(user.username)
    raw_candidates.extend((local_part, f"user-{user.pk}"))
    for raw in raw_candidates:
        normalized = _nickname(raw, allow_reserved=allow_reserved)
        if not normalized:
            continue
        if normalized[1] not in used:
            return normalized, None
        allocated = _suffix_candidate(
            normalized[0],
            user.pk,
            used,
            allow_reserved=allow_reserved,
        )
        return allocated, normalized[1]
    fallback = _suffix_candidate("user", user.pk, used, allow_reserved=True)
    return fallback, None


def _site_owner_id(User):
    owner_key = _email_key(getattr(settings, "SITE_OWNER_EMAIL", ""))
    if not owner_key:
        return None
    matching = [
        user.pk
        for user in User.objects.all().only("pk", "email")
        if _email_key(user.email) == owner_key
    ]
    return matching[0] if len(matching) == 1 else None


def forward(apps, schema_editor):
    User = apps.get_model("users", "User")
    NicknameHistory = apps.get_model("users", "NicknameHistory")
    Comment = apps.get_model("discussions", "Comment")
    PostReaction = apps.get_model("discussions", "PostReaction")
    CommentReaction = apps.get_model("discussions", "CommentReaction")
    BlogPostPage = apps.get_model("blog", "BlogPostPage")
    Page = apps.get_model("wagtailcore", "Page")

    site_owner_id = _site_owner_id(User)
    public_user_ids = set(Comment.objects.values_list("author_id", flat=True))
    public_user_ids.update(PostReaction.objects.values_list("user_id", flat=True))
    public_user_ids.update(CommentReaction.objects.values_list("user_id", flat=True))

    users = list(User.objects.order_by("pk"))
    used_nicknames = set()
    used_emails = {}
    email_keys = {}
    duplicate_emails = []
    for user in users:
        email_key = _email_key(user.email)
        if email_key and email_key not in used_emails:
            used_emails[email_key] = user.pk
            email_keys[user.pk] = email_key
        elif email_key:
            duplicate_emails.append((used_emails[email_key], user.pk))
            email_keys[user.pk] = None
        else:
            email_keys[user.pk] = None

    collisions = []
    confirmed = 0
    incomplete = 0
    nickname_order = sorted(users, key=lambda user: (user.pk != site_owner_id, user.pk))
    for user in nickname_order:
        nickname, collision_key = _candidate_for(
            user,
            used_nicknames,
            site_owner_id=site_owner_id,
        )
        display, nickname_key = nickname
        used_nicknames.add(nickname_key)
        is_confirmed = bool(
            user.is_staff
            or user.is_superuser
            or user.pk == site_owner_id
            or user.pk in public_user_ids
        )
        User.objects.filter(pk=user.pk).update(
            email_normalized=email_keys[user.pk],
            nickname=display,
            nickname_normalized=nickname_key,
            nickname_confirmed=is_confirmed,
            nickname_changed_at=None,
        )
        NicknameHistory.objects.create(
            user_id=user.pk,
            nickname=display,
            nickname_normalized=nickname_key,
            change_kind="backfill",
            reason="Stage 17 deterministic identity backfill",
        )
        if collision_key:
            collisions.append((user.pk, collision_key, nickname_key))
        if is_confirmed:
            confirmed += 1
        else:
            incomplete += 1

    public_posts = BlogPostPage.objects.filter(live=True, first_published_at__isnull=False)
    ownerless_ids = list(public_posts.filter(owner_id__isnull=True).values_list("pk", flat=True))
    owner_backfilled = 0
    if ownerless_ids and site_owner_id is not None:
        owner_backfilled = Page.objects.filter(pk__in=ownerless_ids, owner_id__isnull=True).update(
            owner_id=site_owner_id
        )
    unresolved_owner_ids = list(
        public_posts.filter(owner_id__isnull=True).values_list("pk", flat=True)
    )

    print(
        "Stage 17 identity backfill: "
        f"users={User.objects.count()} confirmed={confirmed} incomplete={incomplete} "
        f"nickname_collisions={len(collisions)} duplicate_email_keys={len(duplicate_emails)} "
        f"public_posts={public_posts.count()} owner_backfilled={owner_backfilled} "
        f"owner_unresolved={len(unresolved_owner_ids)}"
    )
    if collisions:
        print(
            f"Stage 17 nickname collision mapping (user_id, previous_key, final_key): {collisions[:100]}"
        )
    if duplicate_emails:
        print(
            f"Stage 17 duplicate email key user IDs (winner, quarantined): {duplicate_emails[:100]}"
        )
    if unresolved_owner_ids:
        print(f"Stage 17 public posts without an unambiguous owner: {unresolved_owner_ids[:100]}")


def reverse(apps, schema_editor):
    User = apps.get_model("users", "User")
    NicknameHistory = apps.get_model("users", "NicknameHistory")
    NicknameHistory.objects.filter(change_kind="backfill").delete()
    User.objects.update(
        email_normalized=None,
        nickname=None,
        nickname_normalized=None,
        nickname_confirmed=False,
        nickname_changed_at=None,
    )
    # Page-owner repair is intentionally not reversed: restoring a proven,
    # previously missing owner is additive and avoids reintroducing ambiguity.


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0009_emailaddress_unique_primary_email"),
        ("blog", "0005_streamfield_chooser_metadata"),
        ("discussions", "0004_activate_catalog_reaction_identity"),
        ("users", "0002_stage17_identity_expansion"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
