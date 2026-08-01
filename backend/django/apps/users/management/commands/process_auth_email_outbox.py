from django.core.management.base import BaseCommand

from apps.subscriptions.providers import configured_email_provider
from apps.users.auth_email import process_auth_email_batch


class Command(BaseCommand):
    help = "Deliver bounded local-account verification and password-reset email."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=25)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        sent = process_auth_email_batch(
            limit=limit,
            provider=configured_email_provider(),
        )
        self.stdout.write(f"auth_email_sent={sent}")
