import unicodedata
from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_unicode_slug
from rest_framework.exceptions import ValidationError

MAX_QUERY_CODE_POINTS = 200
MAX_TAG_CODE_POINTS = 100
SINGLE_VALUE_PARAMETERS = ("q", "tag", "page", "page_size")


@dataclass(frozen=True)
class PostFilters:
    query: str | None
    tag: str | None


def _contains_control_character(value):
    return any(unicodedata.category(character).startswith("C") for character in value)


def _single_value(query_params, name, errors):
    values = query_params.getlist(name)
    if len(values) > 1:
        errors[name] = ["This parameter may be provided only once."]
        return None
    return values[0] if values else None


def _validate_positive_integer_shape(value, name, errors):
    if value is not None and (
        not value.isascii() or not value.isdecimal() or value.startswith("0")
    ):
        errors[name] = ["This parameter must be a positive integer."]


def parse_post_filters(query_params):
    errors = {}
    values = {name: _single_value(query_params, name, errors) for name in SINGLE_VALUE_PARAMETERS}

    _validate_positive_integer_shape(values["page"], "page", errors)
    _validate_positive_integer_shape(values["page_size"], "page_size", errors)

    raw_query = values["q"]
    query = raw_query.strip() if raw_query is not None else None
    if raw_query is not None and _contains_control_character(raw_query):
        errors["q"] = ["Search queries may not contain control characters."]
    elif query and len(query) > MAX_QUERY_CODE_POINTS:
        errors["q"] = [
            f"Search queries may contain at most {MAX_QUERY_CODE_POINTS} Unicode code points."
        ]
    if not query:
        query = None

    raw_tag = values["tag"]
    tag = raw_tag.strip() if raw_tag is not None else None
    if raw_tag is not None and _contains_control_character(raw_tag):
        errors["tag"] = ["Tag slugs may not contain control characters."]
    elif tag:
        if len(tag) > MAX_TAG_CODE_POINTS:
            errors["tag"] = [
                f"Tag slugs may contain at most {MAX_TAG_CODE_POINTS} Unicode code points."
            ]
        else:
            try:
                validate_unicode_slug(tag)
            except DjangoValidationError:
                errors["tag"] = [
                    "Tag slugs may contain only Unicode letters, numbers, hyphens, and underscores."
                ]
    if not tag:
        tag = None

    if errors:
        raise ValidationError(errors)
    return PostFilters(query=query, tag=tag)
