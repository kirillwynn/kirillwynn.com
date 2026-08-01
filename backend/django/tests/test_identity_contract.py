import pytest
from django.core.exceptions import ValidationError

from apps.users.identity import (
    MAX_NICKNAME_CODE_POINTS,
    RESERVED_NICKNAME_SKELETON_VERSION,
    InvalidNickname,
    normalize_email_address,
    normalize_nickname,
)


@pytest.mark.parametrize(
    ("source", "display", "key"),
    [
        ("  Kirill   Wynn  ", "Kirill Wynn", "kirill wynn"),
        ("A\u00a0B", "A B", "a b"),
        ("A\u030ake", "Åke", "åke"),
        ("\uff21lice", "\uff21lice", "alice"),
        ("Straße", "Straße", "strasse"),
        ("Jean-Luc", "Jean-Luc", "jean-luc"),
        ("O’Connor", "O’Connor", "o’connor"),
        ("\u674e \u96f7", "\u674e \u96f7", "\u674e \u96f7"),
    ],
)
def test_nickname_normalization_contract(source, display, key):
    normalized = normalize_nickname(source)

    assert normalized.display == display
    assert normalized.key == key


@pytest.mark.parametrize(
    "source",
    [
        "a",
        "a" * (MAX_NICKNAME_CODE_POINTS + 1),
        "trailing-",
        "two--separators",
        "<admin>",
        "https://example.com",
        "a\x00b",
        "a\tb",
        "a\nb",
        "a\u2028b",
        "a\u2029b",
        "a\u202eb",
        "a\u2066b",
        "a\u200bb",
        "a\ue000b",
        "a\ufdd0b",
        "a\ufffeb",
        "\ud800x",
        "\u0301\u0301",
        "__",
        "\ufdfa" * 40,
    ],
)
def test_nickname_rejects_unsafe_or_out_of_bounds_values(source):
    with pytest.raises(InvalidNickname):
        normalize_nickname(source)


@pytest.mark.parametrize(
    "source",
    [
        "admin",
        "ADMIN",
        "Ａdmin",
        "аdmin",
        "administrator",
        "moderator",
        "staff",
        "system",
        "support",
        "kirill wynn",
        "Kírill-Wynn",
    ],
)
def test_reserved_and_site_owner_impersonation_boundary(source):
    with pytest.raises(InvalidNickname) as error:
        normalize_nickname(source, reserved_values=("Kirill Wynn",))

    assert error.value.message_dict == {"nickname": ["This nickname is reserved."]}


def test_reserved_skeleton_is_explicitly_versioned_and_not_a_global_script_ban():
    assert RESERVED_NICKNAME_SKELETON_VERSION == "stage17-v1/unicodedata-15.0.0"
    assert normalize_nickname("\u0410лексей").display == "\u0410лексей"
    assert normalize_nickname("山田太郎").display == "山田太郎"


def test_casefold_and_nfkc_collisions_share_one_database_key():
    assert normalize_nickname("Straße").key == normalize_nickname("STRASSE").key
    assert normalize_nickname("Ａlice").key == normalize_nickname("Alice").key


def test_email_normalization_is_case_insensitive_and_idna_aware():
    source, canonical = normalize_email_address("  Reader@Exämple.com  ")

    assert source == "Reader@Exämple.com"
    assert canonical == "reader@xn--exmple-cua.com"
    assert normalize_email_address("READER@XN--EXMPLE-CUA.COM")[1] == canonical


@pytest.mark.parametrize("value", [None, "", "no-at", "a@@example.com", "\ud800@example.com"])
def test_invalid_email_values_have_one_stable_validation_shape(value):
    with pytest.raises(ValidationError) as error:
        normalize_email_address(value)

    assert error.value.message_dict == {"email": ["Enter a valid email address."]}
