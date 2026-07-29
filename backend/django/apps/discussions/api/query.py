from rest_framework.exceptions import ValidationError

MAX_POST_REACTION_BATCH_IDS = 50
MAX_SIGNED_BIGINT = 9_223_372_036_854_775_807


def parse_post_reaction_ids(query_params):
    unexpected = sorted(set(query_params) - {"ids"})
    if unexpected:
        raise ValidationError(
            {"detail": (f"Unexpected query parameter(s): {', '.join(unexpected)}.")}
        )

    values = query_params.getlist("ids")
    if len(values) != 1:
        raise ValidationError({"ids": ["This parameter must be provided exactly once."]})

    raw_ids = values[0]
    parts = raw_ids.split(",")
    if not raw_ids or any(
        not part.isascii()
        or not part.isdecimal()
        or part.startswith("0")
        or len(part) > 19
        or (len(part) == 19 and part > str(MAX_SIGNED_BIGINT))
        for part in parts
    ):
        raise ValidationError(
            {"ids": ["This parameter must be a comma-separated list of positive integers."]}
        )

    if len(parts) > MAX_POST_REACTION_BATCH_IDS:
        raise ValidationError(
            {"ids": [f"At most {MAX_POST_REACTION_BATCH_IDS} IDs may be requested."]}
        )

    ids = [int(part) for part in parts]
    if len(ids) != len(set(ids)):
        raise ValidationError({"ids": ["IDs must be unique."]})
    return ids
