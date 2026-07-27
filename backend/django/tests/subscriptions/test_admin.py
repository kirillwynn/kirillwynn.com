import pytest
from django.contrib.admin.sites import site
from django.test import RequestFactory

from apps.subscriptions.admin import (
    EmailDeliveryAdmin,
    EmailOutboxAdmin,
    SubscriberAdmin,
)
from apps.subscriptions.models import EmailDelivery, EmailOutbox, Subscriber

pytestmark = pytest.mark.django_db


def test_subscription_admin_is_read_only_except_explicit_lifecycle_actions(admin_user):
    request = RequestFactory().get("/django-admin/subscriptions/subscriber/")
    request.user = admin_user
    subscriber_admin = SubscriberAdmin(Subscriber, site)
    outbox_admin = EmailOutboxAdmin(EmailOutbox, site)
    delivery_admin = EmailDeliveryAdmin(EmailDelivery, site)

    assert subscriber_admin.has_add_permission(request) is False
    assert subscriber_admin.has_delete_permission(request) is False
    assert subscriber_admin.actions == (
        "unsubscribe_selected",
        "suppress_selected",
        "unsuppress_selected",
    )
    assert "confirmation_token_version" not in subscriber_admin.fields
    assert "unsubscribe_token_version" not in subscriber_admin.fields
    assert outbox_admin.has_add_permission(request) is False
    assert outbox_admin.has_delete_permission(request) is False
    assert delivery_admin.has_add_permission(request) is False
    assert delivery_admin.has_delete_permission(request) is False
