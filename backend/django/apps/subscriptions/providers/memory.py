import hashlib

from apps.subscriptions.providers.base import EmailProvider, ProviderSendResult


class MemoryEmailProvider(EmailProvider):
    transport_contract_id = "memory.email"
    serializer_contract_version = 1
    sent = []

    def send(self, prepared_request, idempotency_key):
        self.__class__.sent.append((prepared_request, idempotency_key))
        digest = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
        return ProviderSendResult(message_id=f"memory-{digest}")

    @classmethod
    def reset(cls):
        cls.sent = []
