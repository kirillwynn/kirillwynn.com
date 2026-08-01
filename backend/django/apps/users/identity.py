import re
import unicodedata
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

# django-allauth 65.18 stores EmailAddress.email as varchar(254). Keeping the
# public identity boundary at that exact limit prevents a split User/allauth
# identity that one side could persist and the other could not.
MAX_EMAIL_CODE_POINTS = 254
MIN_NICKNAME_CODE_POINTS = 2
MAX_NICKNAME_CODE_POINTS = 40
MAX_NICKNAME_UTF8_BYTES = 160
NICKNAME_PUNCTUATION = frozenset("-_.\u00b7'\u2019")
RESERVED_NICKNAME_SKELETON_VERSION = "stage17-v1/unicodedata-15.0.0"
UNICODE_DATA_VERSION = "15.0.0"
if unicodedata.unidata_version != UNICODE_DATA_VERSION:
    raise RuntimeError(
        "Stage 17 nickname normalization requires Python Unicode data "
        f"{UNICODE_DATA_VERSION}, got {unicodedata.unidata_version}"
    )
RESERVED_NICKNAMES = frozenset(
    {
        "admin",
        "administrator",
        "moderator",
        "staff",
        "system",
        "support",
    }
)

_OPAQUE_USERNAME_RE = re.compile(
    r"^(?:usr_[0-9a-f]{24,}|user[-_]?\d+|(?:google|github)[-_].+)$",
    re.IGNORECASE,
)
_CONFUSABLE_TO_ASCII = str.maketrans(
    {
        # A deliberately narrow, versioned skeleton used only for privileged
        # service names. It is not a general cross-script name restriction.
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

# Unicode 15.0 Default_Ignorable_Code_Point ranges whose members are not
# already rejected by their general-category value. Keeping the complete
# ranges explicit also makes the migration/frontend copies reviewable.
_DEFAULT_IGNORABLE_RANGES = (
    (0x034F, 0x034F),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFFA0, 0xFFA0),
    (0xE0000, 0xE0FFF),
)


class InvalidNickname(ValidationError):
    pass


@dataclass(frozen=True)
class NormalizedNickname:
    display: str
    key: str


def normalize_email_address(value: str) -> tuple[str, str]:
    """Return a display mailbox and one case-insensitive identity key."""

    if not isinstance(value, str):
        raise ValidationError({"email": "Enter a valid email address."})
    source = value.strip()
    if not source or len(source) > MAX_EMAIL_CODE_POINTS or source.count("@") != 1:
        raise ValidationError({"email": "Enter a valid email address."})
    try:
        source.encode("utf-8")
        validate_email(source)
        local, domain = source.rsplit("@", 1)
        ascii_domain = domain.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValidationError):
        raise ValidationError({"email": "Enter a valid email address."}) from None
    canonical = f"{unicodedata.normalize('NFKC', local).casefold()}@{ascii_domain}"
    if len(canonical) > MAX_EMAIL_CODE_POINTS:
        raise ValidationError({"email": "Enter a valid email address."})
    try:
        canonical.encode("utf-8")
        validate_email(canonical)
    except (UnicodeError, ValidationError):
        raise ValidationError({"email": "Enter a valid email address."}) from None
    return source, canonical


def _is_noncharacter(code_point: int) -> bool:
    return 0xFDD0 <= code_point <= 0xFDEF or code_point & 0xFFFF in {0xFFFE, 0xFFFF}


def _is_default_ignorable(code_point: int) -> bool:
    return any(start <= code_point <= end for start, end in _DEFAULT_IGNORABLE_RANGES)


def _collapse_spaces(value: str) -> str:
    pieces: list[str] = []
    pending_space = False
    for character in value:
        if unicodedata.category(character) == "Zs":
            pending_space = bool(pieces)
            continue
        if pending_space:
            pieces.append(" ")
            pending_space = False
        pieces.append(character)
    return "".join(pieces).strip()


def nickname_skeleton(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value).casefold().translate(_CONFUSABLE_TO_ASCII)
    return "".join(
        character
        for character in decomposed
        if not unicodedata.category(character).startswith("M")
        and (character.isalnum() or character in NICKNAME_PUNCTUATION or character == " ")
    ).translate(str.maketrans("", "", "-_.\u00b7'\u2019 "))


def normalize_nickname(
    value: str,
    *,
    reserved_values: tuple[str, ...] | list[str] = (),
    allow_reserved: bool = False,
) -> NormalizedNickname:
    if not isinstance(value, str):
        raise InvalidNickname({"nickname": "Enter a valid nickname."})

    for character in value:
        code_point = ord(character)
        category = unicodedata.category(character)
        if (
            category.startswith("C")
            or category in {"Zl", "Zp"}
            or _is_noncharacter(code_point)
            or _is_default_ignorable(code_point)
        ):
            raise InvalidNickname({"nickname": "Enter a valid nickname."})

    try:
        value.encode("utf-8")
    except UnicodeError:
        raise InvalidNickname({"nickname": "Enter a valid nickname."}) from None

    display = unicodedata.normalize("NFC", _collapse_spaces(value))
    if not MIN_NICKNAME_CODE_POINTS <= len(display) <= MAX_NICKNAME_CODE_POINTS:
        raise InvalidNickname(
            {"nickname": "Nickname must contain between 2 and 40 Unicode characters."}
        )
    if len(display.encode("utf-8")) > MAX_NICKNAME_UTF8_BYTES:
        raise InvalidNickname({"nickname": "Nickname is too large when encoded."})

    previous_separator = False
    cluster_has_base = False
    for index, character in enumerate(display):
        category = unicodedata.category(character)
        is_base = category[0] in {"L", "N"}
        is_mark = category[0] == "M"
        is_separator = character == " " or character in NICKNAME_PUNCTUATION
        if not (is_base or is_mark or is_separator):
            raise InvalidNickname({"nickname": "Enter a valid nickname."})
        if index == 0 and not is_base:
            raise InvalidNickname({"nickname": "Nickname must begin with a letter or number."})
        if is_mark and not cluster_has_base:
            raise InvalidNickname({"nickname": "Enter a valid nickname."})
        if is_separator and previous_separator:
            raise InvalidNickname({"nickname": "Nickname separators may not be repeated."})
        previous_separator = is_separator
        if is_separator:
            cluster_has_base = False
        elif is_base:
            cluster_has_base = True
    if previous_separator:
        raise InvalidNickname({"nickname": "Nickname must end with a letter or number."})

    key = unicodedata.normalize("NFKC", display).casefold()
    if not key or len(key.encode("utf-8")) > MAX_NICKNAME_UTF8_BYTES:
        raise InvalidNickname({"nickname": "Enter a valid nickname."})

    if not allow_reserved:
        reserved_skeletons = {nickname_skeleton(item) for item in RESERVED_NICKNAMES}
        for item in reserved_values:
            try:
                reserved_skeletons.add(
                    nickname_skeleton(normalize_nickname(item, allow_reserved=True).key)
                )
            except InvalidNickname:
                continue
        if nickname_skeleton(key) in reserved_skeletons:
            raise InvalidNickname({"nickname": "This nickname is reserved."})

    return NormalizedNickname(display=display, key=key)


def is_synthetic_username(value: str) -> bool:
    return not value or "@" in value or bool(_OPAQUE_USERNAME_RE.fullmatch(value))
