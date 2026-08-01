import codecs
import json

from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON object key")
        value[key] = item
    return value


def _reject_non_finite(_value):
    raise ValueError("Non-finite JSON number")


def _reject_surrogate_strings(value):
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                raise ValueError("JSON strings may not contain surrogates")
        elif isinstance(current, dict):
            pending.extend(current.keys())
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)


class BoundedJSONParser(BaseParser):
    media_type = "application/json"

    def parse(self, stream, media_type=None, parser_context=None):
        body = stream.read(settings.AUTH_API_MAX_BODY_BYTES + 1)
        if len(body) > settings.AUTH_API_MAX_BODY_BYTES:
            raise ParseError("Request body is too large.")
        try:
            text = codecs.decode(body, "utf-8", errors="strict")
            value = json.loads(
                text,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_non_finite,
            )
            _reject_surrogate_strings(value)
            return value
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
            raise ParseError("Malformed JSON.") from None
