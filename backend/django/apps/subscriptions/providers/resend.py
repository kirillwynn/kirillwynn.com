import json
import urllib.error
import urllib.request

from django.conf import settings

from apps.subscriptions.providers.base import (
    EmailProvider,
    EmailProviderError,
    ProviderSendResult,
    serialize_email_request,
)

RESEND_SEND_URL = "https://api.resend.com/emails"


def serialize_resend_request(message):
    return serialize_email_request(message)


def _read_bounded(response, limit):
    body = response.read(limit + 1)
    if len(body) > limit:
        raise EmailProviderError(
            "Resend returned an oversized response",
            retryable=True,
        )
    return body


def _error_type(response_body):
    try:
        payload = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    error_type = payload.get("name") or payload.get("type")
    return error_type if isinstance(error_type, str) else ""


def _http_error(status, response_body=b""):
    if status == 409:
        error_type = _error_type(response_body)
        if error_type == "invalid_idempotent_request":
            return EmailProviderError(
                "Resend HTTP 409 (invalid_idempotent_request)",
                retryable=False,
                ambiguity_reason="payload_mismatch",
            )
        if error_type == "concurrent_idempotent_requests":
            return EmailProviderError(
                "Resend HTTP 409 (concurrent_idempotent_requests)",
                retryable=True,
                ambiguity_reason="concurrent_request",
            )
        # An unknown conflict is terminal: retrying an unrecognized 409 could
        # conceal a payload/key contract violation.
        return EmailProviderError("Resend HTTP 409 (unknown conflict)", retryable=False)
    return EmailProviderError(
        f"Resend HTTP {status}",
        retryable=status in {408, 425, 429} or status >= 500,
    )


class ResendEmailProvider(EmailProvider):
    transport_contract_id = "resend.emails"
    serializer_contract_version = 1

    def __init__(self, *, opener=None):
        self.opener = opener or urllib.request.urlopen

    def send(self, prepared_request, idempotency_key):
        request = urllib.request.Request(
            RESEND_SEND_URL,
            data=prepared_request.body,
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
                "User-Agent": "kirillwynn.com-email-worker/1",
            },
        )
        try:
            response = self.opener(
                request,
                timeout=settings.EMAIL_PROVIDER_TIMEOUT_SECONDS,
            )
            status = getattr(response, "status", response.getcode())
            response_body = _read_bounded(
                response,
                settings.RESEND_SUCCESS_RESPONSE_MAX_BODY_BYTES,
            )
        except urllib.error.HTTPError as error:
            status = error.code
            try:
                response_body = _read_bounded(
                    error,
                    settings.RESEND_ERROR_RESPONSE_MAX_BODY_BYTES,
                )
            except EmailProviderError:
                raise EmailProviderError(
                    f"Resend HTTP {status} (oversized error response)",
                    retryable=status in {408, 425, 429} or status >= 500,
                ) from None
            raise _http_error(status, response_body) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise EmailProviderError(
                f"Resend network failure ({type(error).__name__})",
                retryable=True,
                ambiguity_reason="transport_failure",
            ) from None
        except EmailProviderError:
            raise
        except Exception as error:  # pragma: no cover - defensive adapter boundary
            raise EmailProviderError(
                f"Resend adapter failure ({type(error).__name__})",
                retryable=True,
            ) from None

        if not 200 <= status < 300:
            raise _http_error(status, response_body)
        try:
            payload = json.loads(response_body)
            message_id = payload["id"]
        except (json.JSONDecodeError, KeyError, TypeError):
            raise EmailProviderError(
                "Resend returned an invalid success response",
                retryable=True,
            ) from None
        if not isinstance(message_id, str) or not message_id or len(message_id) > 255:
            raise EmailProviderError(
                "Resend returned an invalid message identifier",
                retryable=True,
            )
        return ProviderSendResult(message_id=message_id)
