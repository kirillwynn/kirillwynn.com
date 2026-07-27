import json
from dataclasses import dataclass, field

from django.conf import settings

from config.email_settings import normalize_transport_identity

MAX_PROVIDER_REQUEST_BODY_BYTES = 1_048_576


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


@dataclass(frozen=True)
class TransportIdentity:
    contract_id: str
    serializer_version: int
    idempotency_namespace: str

    def __post_init__(self):
        if (
            normalize_transport_identity(
                self.contract_id,
                name="transport contract identifier",
            )
            != self.contract_id
        ):
            raise ValueError("transport contract identifier must already be normalized")
        if (
            normalize_transport_identity(
                self.idempotency_namespace,
                name="idempotency namespace",
            )
            != self.idempotency_namespace
        ):
            raise ValueError("idempotency namespace must already be normalized")
        if (
            not isinstance(self.serializer_version, int)
            or isinstance(self.serializer_version, bool)
            or not 1 <= self.serializer_version <= 32_767
        ):
            raise ValueError("serializer contract version must be between 1 and 32767")


@dataclass(frozen=True)
class PreparedEmailRequest:
    body: bytes
    transport: TransportIdentity

    def __post_init__(self):
        if (
            not isinstance(self.body, bytes)
            or not self.body
            or len(self.body) > MAX_PROVIDER_REQUEST_BODY_BYTES
        ):
            raise ValueError("email provider request body must be bounded non-empty bytes")


class EmailProviderError(Exception):
    def __init__(self, safe_message, *, retryable, ambiguity_reason="provider_failure"):
        self.safe_message = safe_message[:500]
        self.retryable = retryable
        self.ambiguity_reason = ambiguity_reason
        super().__init__(self.safe_message)


def serialize_email_request(message):
    return json.dumps(
        {
            "from": message.from_email,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
            "headers": message.headers,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


class EmailProvider:
    transport_contract_id = None
    serializer_contract_version = None

    def transport_identity(self):
        contract_id = normalize_transport_identity(
            self.transport_contract_id,
            name="transport contract identifier",
        )
        namespace = normalize_transport_identity(
            settings.EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE,
            name="idempotency namespace",
        )
        version = self.serializer_contract_version
        return TransportIdentity(
            contract_id=contract_id,
            serializer_version=version,
            idempotency_namespace=namespace,
        )

    def serialize_request(self, message):
        """Return deterministic request bytes for the declared serializer version."""

        return serialize_email_request(message)

    def prepare_request(self, message):
        body = self.serialize_request(message)
        return PreparedEmailRequest(
            body=body,
            transport=self.transport_identity(),
        )

    def send(self, prepared_request, idempotency_key):
        """Perform provider I/O with the already verified immutable request bytes."""

        raise NotImplementedError
