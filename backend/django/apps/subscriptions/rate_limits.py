import hashlib
import hmac
import ipaddress
import math

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.subscriptions.models import SubscriptionRateLimitBucket


class SubscriptionRateLimitExceeded(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, math.ceil(retry_after))
        super().__init__("Subscription rate limit exceeded.")


def client_ip(request):
    remote = request.META.get("REMOTE_ADDR", "")
    try:
        remote = str(ipaddress.ip_address(remote))
    except ValueError:
        remote = "unknown"

    trusted_proxy_count = settings.ALLAUTH_TRUSTED_PROXY_COUNT
    if trusted_proxy_count <= 0:
        return remote
    forwarded = [
        value.strip()
        for value in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        if value.strip()
    ]
    chain = [*forwarded, remote]
    if len(chain) <= trusted_proxy_count:
        return remote
    candidate = chain[-(trusted_proxy_count + 1)]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return remote


def _hashed_key(scope, value):
    return hmac.new(
        settings.SUBSCRIPTION_SIGNING_SECRET.encode(),
        f"{scope}\0{value}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _policy(scope):
    if scope == SubscriptionRateLimitBucket.Scope.CONFIRM_IP:
        return (
            settings.SUBSCRIPTION_CONFIRM_RATE_LIMIT_COUNT,
            settings.SUBSCRIPTION_CONFIRM_RATE_LIMIT_WINDOW_SECONDS,
        )
    return (
        settings.SUBSCRIPTION_RATE_LIMIT_COUNT,
        settings.SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS,
    )


def _lock_bucket_key(key_hash):
    if connection.vendor != "postgresql":
        return
    lock_key = int.from_bytes(
        bytes.fromhex(key_hash[:16]),
        byteorder="big",
        signed=True,
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_key])


def consume_rate_limit(*, scope, value, at=None):
    limit, window_seconds = _policy(scope)
    now = at or timezone.now()
    key_hash = _hashed_key(scope, value)
    with transaction.atomic():
        # Anonymous buckets have no durable parent row to lock before the
        # first insert. Serialize the HMAC-keyed bucket for this transaction.
        _lock_bucket_key(key_hash)
        try:
            bucket = SubscriptionRateLimitBucket.objects.select_for_update().get(
                scope=scope,
                key_hash=key_hash,
            )
        except SubscriptionRateLimitBucket.DoesNotExist:
            try:
                with transaction.atomic():
                    bucket = SubscriptionRateLimitBucket.objects.create(
                        scope=scope,
                        key_hash=key_hash,
                        window_started_at=now,
                        request_count=0,
                    )
            except IntegrityError:
                bucket = SubscriptionRateLimitBucket.objects.select_for_update().get(
                    scope=scope,
                    key_hash=key_hash,
                )

        elapsed = (now - bucket.window_started_at).total_seconds()
        if elapsed >= window_seconds or elapsed < 0:
            bucket.window_started_at = now
            bucket.request_count = 0
        elif bucket.request_count >= limit:
            raise SubscriptionRateLimitExceeded(window_seconds - elapsed)
        bucket.request_count += 1
        bucket.save(update_fields=("window_started_at", "request_count"))
