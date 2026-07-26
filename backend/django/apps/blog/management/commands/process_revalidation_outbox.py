from django.core.management.base import BaseCommand, CommandError

from apps.blog.services.revalidation import deliver_event, pending_event_ids


class Command(BaseCommand):
    help = "Deliver pending signed cache-revalidation events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1_000:
            raise CommandError("--limit must be between 1 and 1000")

        event_ids = pending_event_ids(limit=limit)
        delivered = sum(deliver_event(event_id) for event_id in event_ids)
        failed = len(event_ids) - delivered
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {len(event_ids)} event(s): {delivered} delivered, {failed} pending."
            )
        )
