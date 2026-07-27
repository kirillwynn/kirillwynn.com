from django.urls import path

from apps.subscriptions.api.views import (
    ConfirmSubscriptionAPIView,
    SubscribeAPIView,
    UnsubscribeAPIView,
    resend_webhook,
    unsubscribe_one_click,
)

app_name = "subscriptions_api"

urlpatterns = [
    path("subscriptions/", SubscribeAPIView.as_view(), name="subscribe"),
    path(
        "subscriptions/confirm/",
        ConfirmSubscriptionAPIView.as_view(),
        name="confirm",
    ),
    path(
        "subscriptions/unsubscribe/",
        UnsubscribeAPIView.as_view(),
        name="unsubscribe",
    ),
    path(
        "subscriptions/unsubscribe/one-click/",
        unsubscribe_one_click,
        name="unsubscribe-one-click",
    ),
    path("email/webhooks/resend/", resend_webhook, name="resend-webhook"),
]
