from datetime import UTC

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST
from rest_framework.exceptions import APIException, UnsupportedMediaType, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from svix.webhooks import Webhook, WebhookVerificationError

from apps.subscriptions.models import (
    EmailWebhookEvent,
    SubscriptionRateLimitBucket,
    normalize_email_address,
)
from apps.subscriptions.rate_limits import (
    SubscriptionRateLimitExceeded,
    client_ip,
    consume_rate_limit,
)
from apps.subscriptions.services import (
    confirm_subscription,
    request_subscription,
    unsubscribe_with_credential,
)
from apps.subscriptions.tokens import InvalidSubscriptionCredential
from apps.subscriptions.webhooks import (
    RECOGNIZED_DELIVERY_EVENTS,
    normalized_bounce_type,
    reconcile_pending_webhooks,
    webhook_event_defaults,
)

GENERIC_SUBSCRIBE_DETAIL = "If the address can be subscribed, a confirmation email will be sent."
INVALID_CREDENTIAL_DETAIL = "This link is invalid or expired."


class SubscriptionThrottled(APIException):
    status_code = 429
    default_detail = "Too many requests. Please try again later."
    default_code = "subscription_rate_limited"

    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__()


def _validate_payload(request, *, allowed):
    if request.content_type != "application/json":
        raise UnsupportedMediaType(request.content_type or "unknown")
    if not isinstance(request.data, dict):
        raise ValidationError({"detail": "A JSON object is required."})
    unexpected = set(request.data) - set(allowed)
    if unexpected:
        raise ValidationError({"detail": f"Unexpected field(s): {', '.join(sorted(unexpected))}."})


class SubscriptionAPIViewMixin:
    permission_classes = [AllowAny]
    http_method_names = ["post", "options"]

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            detail = getattr(exc, "message_dict", None) or {"detail": "The request is invalid."}
            exc = ValidationError(detail)
        elif isinstance(exc, SubscriptionRateLimitExceeded):
            exc = SubscriptionThrottled(exc.retry_after)
        response = super().handle_exception(exc)
        if isinstance(exc, SubscriptionThrottled):
            response["Retry-After"] = str(exc.retry_after)
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        patch_cache_control(response, private=True, no_store=True)
        patch_vary_headers(response, ["Cookie"])
        exception = getattr(response, "exception", None)
        if isinstance(exception, SubscriptionThrottled):
            response["Retry-After"] = str(exception.retry_after)
        return response

    @staticmethod
    def consume(scope, value):
        try:
            consume_rate_limit(scope=scope, value=value)
        except SubscriptionRateLimitExceeded as error:
            raise SubscriptionThrottled(error.retry_after) from error


@method_decorator(csrf_protect, name="dispatch")
class SubscribeAPIView(SubscriptionAPIViewMixin, APIView):
    def post(self, request):
        _validate_payload(request, allowed={"email"})
        if "email" not in request.data:
            raise ValidationError({"email": "This field is required."})
        self.consume(
            SubscriptionRateLimitBucket.Scope.SUBSCRIBE_IP,
            client_ip(request),
        )
        source, canonical = normalize_email_address(request.data["email"])
        self.consume(
            SubscriptionRateLimitBucket.Scope.SUBSCRIBE_EMAIL,
            canonical,
        )
        request_subscription(source)
        return Response({"detail": GENERIC_SUBSCRIBE_DETAIL}, status=202)


@method_decorator(csrf_protect, name="dispatch")
class ConfirmSubscriptionAPIView(SubscriptionAPIViewMixin, APIView):
    def post(self, request):
        _validate_payload(request, allowed={"credential"})
        credential = request.data.get("credential")
        self.consume(
            SubscriptionRateLimitBucket.Scope.CONFIRM_IP,
            client_ip(request),
        )
        try:
            _, changed = confirm_subscription(credential)
        except InvalidSubscriptionCredential:
            raise ValidationError({"detail": INVALID_CREDENTIAL_DETAIL}) from None
        return Response(
            {"status": "confirmed" if changed else "already_confirmed"},
        )


@method_decorator(csrf_protect, name="dispatch")
class UnsubscribeAPIView(SubscriptionAPIViewMixin, APIView):
    def post(self, request):
        _validate_payload(request, allowed={"credential"})
        try:
            _, changed = unsubscribe_with_credential(request.data.get("credential"))
        except InvalidSubscriptionCredential:
            raise ValidationError({"detail": INVALID_CREDENTIAL_DETAIL}) from None
        return Response(
            {"status": "unsubscribed" if changed else "already_unsubscribed"},
        )


@csrf_exempt
@require_POST
def unsubscribe_one_click(request):
    if request.content_type != "application/x-www-form-urlencoded":
        return HttpResponse(status=415)
    if request.body != b"List-Unsubscribe=One-Click":
        return HttpResponse(status=400)
    try:
        unsubscribe_with_credential(request.GET.get("credential"))
    except InvalidSubscriptionCredential:
        # The boundary remains idempotent and does not disclose token validity
        # to automated mail clients.
        pass
    response = HttpResponse(status=200)
    patch_cache_control(response, private=True, no_store=True)
    return response


def _webhook_body(request):
    raw_length = request.META.get("CONTENT_LENGTH", "")
    try:
        content_length = int(raw_length) if raw_length else 0
    except ValueError:
        raise ValueError from None
    if content_length > settings.RESEND_WEBHOOK_MAX_BODY_BYTES:
        raise RequestDataTooBig
    body = request.body
    if len(body) > settings.RESEND_WEBHOOK_MAX_BODY_BYTES:
        raise RequestDataTooBig
    return body


def _webhook_headers(request):
    event_id = request.headers.get("svix-id", "")
    timestamp = request.headers.get("svix-timestamp", "")
    signature = request.headers.get("svix-signature", "")
    if (
        not event_id
        or len(event_id) > 255
        or not timestamp
        or not signature
        or len(signature) > 2_048
    ):
        raise WebhookVerificationError("Missing or invalid signature headers")
    try:
        timestamp_value = float(timestamp)
    except ValueError:
        raise WebhookVerificationError("Invalid timestamp") from None
    if abs(timezone.now().timestamp() - timestamp_value) > (
        settings.RESEND_WEBHOOK_TIMESTAMP_WINDOW_SECONDS
    ):
        raise WebhookVerificationError("Timestamp outside replay window")
    return event_id, {
        "svix-id": event_id,
        "svix-timestamp": timestamp,
        "svix-signature": signature,
    }


def _provider_timestamp(value):
    if not isinstance(value, str):
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


@csrf_exempt
@require_POST
def resend_webhook(request):
    try:
        raw_body = _webhook_body(request)
    except RequestDataTooBig:
        return HttpResponse(status=413)
    except ValueError:
        return HttpResponse(status=400)
    try:
        event_id, signature_headers = _webhook_headers(request)
        # Svix verifies the exact raw bytes and timestamp before deserializing.
        payload = Webhook(settings.RESEND_WEBHOOK_SECRET).verify(
            raw_body,
            signature_headers,
        )
    except (WebhookVerificationError, ValueError, UnicodeError):
        return HttpResponse(status=400)
    if not isinstance(payload, dict):
        return HttpResponse(status=400)

    event_type = payload.get("type")
    data = payload.get("data")
    if not isinstance(event_type, str) or not isinstance(data, dict):
        return HttpResponse(status=400)
    occurred_at = _provider_timestamp(payload.get("created_at"))
    now = timezone.now()
    provider_message_id = data.get("email_id")
    if (
        not isinstance(provider_message_id, str)
        or not provider_message_id
        or len(provider_message_id) > 255
    ):
        provider_message_id = None
    bounce_type = (
        normalized_bounce_type(data)
        if event_type == "email.bounced" and provider_message_id is not None
        else ""
    )

    with transaction.atomic():
        webhook_event, created = EmailWebhookEvent.objects.get_or_create(
            provider="resend",
            event_id=event_id,
            defaults=webhook_event_defaults(
                event_type=event_type[:80],
                provider_message_id=provider_message_id,
                occurred_at=occurred_at,
                bounce_type=bounce_type,
                at=now,
            ),
        )
    if (
        webhook_event.processing_state == EmailWebhookEvent.ProcessingState.PENDING
        and webhook_event.provider_message_id is not None
        and (created or event_type in RECOGNIZED_DELIVERY_EVENTS)
    ):
        reconcile_pending_webhooks(provider_message_id=webhook_event.provider_message_id)
    return HttpResponse(status=200)
