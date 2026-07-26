import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


def test_user_email_is_unique():
    user_model = get_user_model()
    user_model.objects.create_user(username="first", email="reader@example.com")

    with pytest.raises(IntegrityError), transaction.atomic():
        user_model.objects.create_user(username="second", email="reader@example.com")


def test_user_is_not_banned_by_default():
    user = get_user_model().objects.create_user(username="reader", email="reader@example.com")

    assert user.is_banned is False
