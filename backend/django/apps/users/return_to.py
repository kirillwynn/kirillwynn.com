import re
from urllib.parse import unquote, urlsplit

from django.utils.http import url_has_allowed_host_and_scheme

POST_PATH_RE = re.compile(r"^/posts/[\w-]+$", re.UNICODE)
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
MALFORMED_PERCENT_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def has_exactly_one_leading_slash(value: str) -> bool:
    return value.startswith("/") and not value.startswith("//")


def safe_return_to(value: str | None, fallback: str = "/") -> str:
    """Return an allowlisted public frontend route, or the fallback."""
    if not value or not isinstance(value, str):
        return fallback
    if (
        not has_exactly_one_leading_slash(value)
        or CONTROL_RE.search(value)
        or "\\" in value
        or MALFORMED_PERCENT_RE.search(value)
    ):
        return fallback

    try:
        decoded = unquote(value, encoding="utf-8", errors="strict")
        if (
            MALFORMED_PERCENT_RE.search(decoded)
            or unquote(decoded, encoding="utf-8", errors="strict") != decoded
        ):
            return fallback
        parsed = urlsplit(decoded)
    except (UnicodeError, ValueError):
        return fallback

    if (
        not has_exactly_one_leading_slash(decoded)
        or CONTROL_RE.search(decoded)
        or "\\" in decoded
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or not url_has_allowed_host_and_scheme(
            decoded,
            allowed_hosts=set(),
            require_https=True,
        )
    ):
        return fallback

    if parsed.path in {"/", "/bridge", "/account"} or POST_PATH_RE.fullmatch(parsed.path):
        return decoded
    return fallback


def is_safe_return_to(value: str | None) -> bool:
    return bool(value) and bool(safe_return_to(value, fallback=""))
