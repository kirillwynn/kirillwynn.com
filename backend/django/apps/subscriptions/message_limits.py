MAX_EMAIL_SUBJECT_LENGTH = 512
MAX_PUBLIC_ORIGIN_LENGTH = 2_048
MAX_PUBLICATION_TITLE_LENGTH = 255
MAX_PUBLICATION_EXCERPT_LENGTH = 320
MAX_SNAPSHOT_URL_LENGTH = 8_192


def bounded_snapshot_value(value, *, name, max_length, allow_blank=False):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    if (not value and not allow_blank) or len(value) > max_length:
        raise ValueError(f"{name} exceeds its immutable snapshot boundary")
    return value
