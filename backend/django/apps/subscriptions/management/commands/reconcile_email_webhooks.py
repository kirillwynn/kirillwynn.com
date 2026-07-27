from django.core.management.base import BaseCommand, CommandError

from apps.subscriptions.webhooks import (
    delete_expired_webhook_history,
    expire_unmatched_webhooks,
    reconcile_pending_webhooks,
)


class Command(BaseCommand):
    help = "Reconcile and retain a bounded batch of authenticated email webhooks."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1_000:
            raise CommandError("--limit must be between 1 and 1000")
        applied = reconcile_pending_webhooks(limit=limit)
        expired = expire_unmatched_webhooks(limit=limit)
        deleted = delete_expired_webhook_history(limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"Reconciled {applied}, expired {expired}, deleted {deleted} webhook event(s)."
            )
        )
