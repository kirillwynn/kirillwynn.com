import json
import urllib.error
import urllib.request

from django.conf import settings

from apps.subscriptions.providers.base import (
    EmailProvider,
    EmailProviderError,
    ProviderSendResult,
)

RESEND_SEND_URL = "https://api.resend.com/emails"


class ResendEmailProvider(EmailProvider):
    def __init__(self, *, opener=None):
        self.opener = opener or urllib.request.urlopen

    def send(self, message, idempotency_key):
        body = json.dumps(
            {
                "from": settings.RESEND_FROM_EMAIL,
                "to": [message.to],
                "subject": message.subject,
                "text": message.text,
                "html": message.html,
                "headers": message.headers,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        request = urllib.request.Request(
            RESEND_SEND_URL,
            data=body,
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
            response_body = response.read()
        except urllib.error.HTTPError as error:
            status = error.code
            retryable = status in {408, 409, 425, 429} or status >= 500
            raise EmailProviderError(
                f"Resend HTTP {status}",
                retryable=retryable,
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise EmailProviderError(
                f"Resend network failure ({type(error).__name__})",
                retryable=True,
            ) from None
        except Exception as error:  # pragma: no cover - defensive adapter boundary
            raise EmailProviderError(
                f"Resend adapter failure ({type(error).__name__})",
                retryable=True,
            ) from None

        if not 200 <= status < 300:
            raise EmailProviderError(
                f"Resend HTTP {status}",
                retryable=status in {408, 409, 425, 429} or status >= 500,
            )
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
