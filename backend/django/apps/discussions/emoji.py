import unicodedata

import emoji
from django.core.exceptions import ValidationError

MAX_EMOJI_CODE_POINTS = 32
MAX_EMOJI_UTF8_BYTES = 128

_FORBIDDEN_FORMAT_CONTROLS = {
    "\u061c",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}


def normalize_emoji(value):
    """Return one canonical NFC RGI emoji sequence or raise ValidationError."""

    if not isinstance(value, str):
        raise ValidationError({"emoji": "This field must be a string."})
    if not value:
        raise ValidationError({"emoji": "An emoji is required."})
    if len(value) > MAX_EMOJI_CODE_POINTS:
        raise ValidationError(
            {"emoji": f"Emoji cannot exceed {MAX_EMOJI_CODE_POINTS} Unicode code points."}
        )
    if len(value.encode("utf-8")) > MAX_EMOJI_UTF8_BYTES:
        raise ValidationError({"emoji": f"Emoji cannot exceed {MAX_EMOJI_UTF8_BYTES} UTF-8 bytes."})
    for character in value:
        category = unicodedata.category(character)
        if (
            character.isspace()
            or category in {"Cc", "Cs"}
            or character in _FORBIDDEN_FORMAT_CONTROLS
        ):
            raise ValidationError(
                {"emoji": "Emoji contains whitespace or a forbidden control character."}
            )

    normalized = unicodedata.normalize("NFC", value)
    data = emoji.EMOJI_DATA.get(normalized)
    if (
        not emoji.is_emoji(normalized)
        or data is None
        or data.get("status") == emoji.STATUS["component"]
    ):
        raise ValidationError({"emoji": "Enter exactly one standard Unicode emoji sequence."})
    return normalized
