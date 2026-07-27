from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmailMessage:
    from_email: str
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
    def __init__(self, safe_message, *, retryable, ambiguity_reason="provider_failure"):
        self.safe_message = safe_message[:500]
        self.retryable = retryable
        self.ambiguity_reason = ambiguity_reason
        super().__init__(self.safe_message)


class EmailProvider:
    def send(self, message, idempotency_key):
        raise NotImplementedError
