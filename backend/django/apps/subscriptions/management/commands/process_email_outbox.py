from django.core.management.base import BaseCommand, CommandError

from apps.subscriptions.models import EmailOutbox
from apps.subscriptions.outbox import claim_outbox_batch, process_outbox_event
from apps.subscriptions.providers import configured_email_provider


class Command(BaseCommand):
    help = "Process a bounded batch from the durable email outbox."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)
        parser.add_argument("--delivery-limit", type=int, default=None)

    def handle(self, *args, **options):
        limit = options["limit"]
        delivery_limit = options["delivery_limit"]
        if not 1 <= limit <= 1_000:
            raise CommandError("--limit must be between 1 and 1000")
        if delivery_limit is not None and not 1 <= delivery_limit <= 1_000:
            raise CommandError("--delivery-limit must be between 1 and 1000")

        provider = configured_email_provider()
        event_ids = claim_outbox_batch(limit=limit)
        sent = 0
        outcomes = {choice: 0 for choice, _ in EmailOutbox.Status.choices}
        for event_id in event_ids:
            event_sent, status = process_outbox_event(
                event_id,
                provider=provider,
                delivery_limit=delivery_limit,
            )
            sent += event_sent
            outcomes[status] += 1
        self.stdout.write(
            self.style.SUCCESS(
                "Processed "
                f"{len(event_ids)} event(s), accepted {sent} message(s): "
                f"{outcomes[EmailOutbox.Status.DELIVERED]} delivered, "
                f"{outcomes[EmailOutbox.Status.PENDING]} pending, "
                f"{outcomes[EmailOutbox.Status.FAILED]} failed."
            )
        )
