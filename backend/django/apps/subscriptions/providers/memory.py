import hashlib

from apps.subscriptions.providers.base import EmailProvider, ProviderSendResult


class MemoryEmailProvider(EmailProvider):
    sent = []

    def send(self, message, idempotency_key):
        self.__class__.sent.append((message, idempotency_key))
        digest = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
        return ProviderSendResult(message_id=f"memory-{digest}")

    @classmethod
    def reset(cls):
        cls.sent = []
