from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderSendResult:
    message_id: str
    created_at: object | None = None


class EmailProviderError(Exception):
    def __init__(self, safe_message, *, retryable):
        self.safe_message = safe_message[:500]
        self.retryable = retryable
        super().__init__(self.safe_message)


class EmailProvider:
    def send(self, message, idempotency_key):
        raise NotImplementedError
