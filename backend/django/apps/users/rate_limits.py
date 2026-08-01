import hashlib
import hmac
import math
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.users.models import AuthRateLimitBucket


class AuthRateLimitExceeded(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, math.ceil(retry_after))
        super().__init__("Auth rate limit exceeded")


def _policy(scope):
    try:
        return settings.AUTH_RATE_LIMITS[scope]
    except KeyError:
        raise ValueError("Unknown auth rate-limit scope") from None


def _key_digest(scope, value):
    payload = f"stage17-auth-rate|{scope}|{value}".encode()
    return hmac.new(
        settings.AUTH_RATE_LIMIT_SIGNING_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()


def consume_auth_rate_limit(*, scope, value, at=None):
    limit, window_seconds = _policy(scope)
    now = at or timezone.now()
    window_epoch = int(now.timestamp()) // window_seconds * window_seconds
    window_start = datetime.fromtimestamp(window_epoch, tz=UTC)
    key_digest = _key_digest(scope, value)
    with transaction.atomic():
        created = False
        try:
            bucket = AuthRateLimitBucket.objects.select_for_update().get(
                scope=scope,
                key_digest=key_digest,
                window_started_at=window_start,
            )
        except AuthRateLimitBucket.DoesNotExist:
            try:
                with transaction.atomic():
                    bucket = AuthRateLimitBucket.objects.create(
                        scope=scope,
                        key_digest=key_digest,
                        window_started_at=window_start,
                    )
                    created = True
            except IntegrityError:
                bucket = AuthRateLimitBucket.objects.select_for_update().get(
                    scope=scope,
                    key_digest=key_digest,
                    window_started_at=window_start,
                )
        if bucket.request_count >= limit:
            raise AuthRateLimitExceeded(window_seconds - (now - window_start).total_seconds())
        bucket.request_count += 1
        bucket.save(update_fields=("request_count",))
        if created:
            # Fixed-window rows are intentionally independent for contention
            # safety. Bound their lifecycle opportunistically without a
            # process-local scheduler or an unbounded delete in a web request.
            # Two complete windows are retained so an in-flight boundary
            # request is never targeted by cleanup.
            stale_ids = list(
                AuthRateLimitBucket.objects.filter(
                    scope=scope,
                    window_started_at__lt=window_start - timedelta(seconds=window_seconds * 2),
                )
                .order_by("window_started_at", "pk")
                .values_list("pk", flat=True)[:1000]
            )
            if stale_ids:
                AuthRateLimitBucket.objects.filter(pk__in=stale_ids).delete()
