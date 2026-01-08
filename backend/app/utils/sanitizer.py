from __future__ import annotations

import bleach
from bleach.html5lib_shim import Filter


ALLOWED_TAGS = [
    "p",
    "br",
    "h1",
    "h2",
    "h3",
    "strong",
    "em",
    "s",
    "u",
    "mark",
    "sup",
    "sub",
    "blockquote",
    "ul",
    "ol",
    "li",
    "pre",
    "code",
    "hr",
    "a",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "*": ["class"],
}


class TargetBlankRelFilter(Filter):
    def __iter__(self):
        for token in super().__iter__():
            if token["type"] == "StartTag" and token["name"] == "a":
                attrs = dict(token["data"])
                if attrs.get("target") == "_blank":
                    rel_tokens = set((attrs.get("rel") or "").split())
                    rel_tokens.update({"noopener", "noreferrer"})
                    attrs["rel"] = " ".join(sorted(rel_tokens))
                token["data"] = [(k, v) for k, v in attrs.items()]
            yield token


_cleaner = bleach.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    strip=True,
    filters=[TargetBlankRelFilter],
)


def sanitize_html(raw_html: str | None) -> str:
    """Return sanitized HTML safe for rendering."""

    return _cleaner.clean(raw_html or "")


def generate_excerpt(html: str, length: int = 200) -> str:
    """Generate a short excerpt from HTML content."""

    plain_text = bleach.clean(html or "", tags=[], attributes={}, strip=True)
    plain_text = " ".join(plain_text.split())
    if len(plain_text) <= length:
        return plain_text
    return plain_text[:length].rstrip() + "…"
