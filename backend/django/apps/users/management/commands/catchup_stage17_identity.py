from importlib import import_module

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder

ACTIVATION_MIGRATION = "0005_stage17_activation_catchup"


class Command(BaseCommand):
    help = "Idempotently repair users created by a rollback digest after Stage 17 activation."

    def handle(self, *args, **options):
        if ("users", ACTIVATION_MIGRATION) not in MigrationRecorder(
            connection
        ).applied_migrations():
            raise CommandError("Stage 17 activation migration is not applied")

        # The migration stays self-contained for historical reproducibility.
        # Reusing its exact idempotent data function here prevents the normal
        # rollback -> old OAuth signup -> roll-forward path from drifting to a
        # second nickname/owner algorithm.
        migration = import_module(f"apps.users.migrations.{ACTIVATION_MIGRATION}")
        with transaction.atomic():
            migration.forward(apps, None)
        self.stdout.write("stage17_identity_catchup=complete")
