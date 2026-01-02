"""Minimal email validation helpers used by WTForms."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

__all__ = ["EmailNotValidError", "validate_email", "ValidatedEmail", "CachingResolver"]
__version__ = "2.2.0"


class EmailNotValidError(ValueError):
    """Raised when an email address fails validation."""


@dataclass
class ValidatedEmail:
    original: str
    email: str
    local_part: str
    domain: str
    ascii_email: str
    ascii_local_part: str
    ascii_domain: str


class CachingResolver:
    """Placeholder to mirror the third-party API (no DNS lookups)."""

    def __call__(self, domain: str) -> Optional[str]:  # pragma: no cover - shim only
        return None


_SIMPLE_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(
    email: str,
    *,
    check_deliverability: bool | None = False,
    allow_smtputf8: bool | None = True,
    allow_empty_local: bool | None = False,
):
    """Validate email address syntax.

    This is a lightweight stand-in for the `email_validator` package and only
    enforces basic structure and non-empty components. Domain deliverability is
    not checked to keep the shim self-contained.
    """

    if email is None:
        raise EmailNotValidError("An email address is required.")

    candidate = email.strip()
    if not candidate:
        raise EmailNotValidError("An email address is required.")

    if not allow_empty_local and candidate.startswith("@"):
        raise EmailNotValidError("The email address is missing a local part before '@'.")

    if not _SIMPLE_EMAIL_RE.match(candidate):
        raise EmailNotValidError("The email address is not valid.")

    local_part, domain = candidate.rsplit("@", 1)
    normalized = candidate.lower()

    return ValidatedEmail(
        original=email,
        email=candidate,
        local_part=local_part,
        domain=domain,
        ascii_email=normalized,
        ascii_local_part=local_part.lower(),
        ascii_domain=domain.lower(),
    )
