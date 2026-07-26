import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.base import positive_int


@pytest.mark.parametrize("value", ["", " ", "0", "-1", "1.5", "many"])
def test_comment_rate_limit_configuration_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("COMMENT_TEST_RATE", value)

    with pytest.raises(ImproperlyConfigured):
        positive_int("COMMENT_TEST_RATE", "10")


def test_comment_rate_limit_configuration_accepts_trimmed_positive_integer(monkeypatch):
    monkeypatch.setenv("COMMENT_TEST_RATE", " 12 ")

    assert positive_int("COMMENT_TEST_RATE", "10") == 12
