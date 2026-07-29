from pathlib import Path

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.discussions.catalog_pipeline import (
    CatalogPipelineError,
    S3ReactionObjectStore,
    sync_catalog,
)


class Command(BaseCommand):
    help = "Upload and verify attested reaction objects, then optionally activate the catalog."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True, type=Path)
        parser.add_argument("--attestation", required=True, type=Path)
        parser.add_argument(
            "--environment",
            required=True,
            choices=("staging", "production"),
        )
        parser.add_argument("--activate", action="store_true")

    def handle(self, *args, **options):
        try:
            result = sync_catalog(
                manifest_path=options["manifest"],
                attestation_path=options["attestation"],
                environment=options["environment"],
                object_store=S3ReactionObjectStore(
                    default_storage,
                    environment=options["environment"],
                ),
                imported_at=timezone.now(),
                activate=options["activate"],
            )
        except (CatalogPipelineError, OSError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(str(result)))
