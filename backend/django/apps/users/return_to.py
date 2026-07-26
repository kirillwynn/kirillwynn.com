import re
from urllib.parse import unquote, urlsplit

POST_PATH_RE = re.compile(r"^/posts/[\w-]+$", re.UNICODE)
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def safe_return_to(value: str | None, fallback: str = "/") -> str:
    """Return an allowlisted public frontend route, or the fallback."""
    if not value or not isinstance(value, str):
        return fallback
    if CONTROL_RE.search(value) or "\\" in value:
        return fallback

    try:
        decoded = unquote(value, errors="strict")
        if unquote(decoded, errors="strict") != decoded:
            return fallback
        parsed = urlsplit(decoded)
    except (UnicodeError, ValueError):
        return fallback

    if (
        CONTROL_RE.search(decoded)
        or "\\" in decoded
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
    ):
        return fallback

    if parsed.path in {"/", "/bridge", "/account"} or POST_PATH_RE.fullmatch(parsed.path):
        return decoded
    return fallback


def is_safe_return_to(value: str | None) -> bool:
    return bool(value) and bool(safe_return_to(value, fallback=""))
