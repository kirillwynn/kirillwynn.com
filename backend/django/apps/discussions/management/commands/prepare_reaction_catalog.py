from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.discussions.catalog_pipeline import CatalogPipelineError, prepare_catalog


class Command(BaseCommand):
    help = "Validate an explicit reaction manifest and prepare deterministic immutable assets."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True, type=Path)
        parser.add_argument("--source-root", required=True, type=Path)
        parser.add_argument("--output-dir", required=True, type=Path)
        parser.add_argument("--reuse-attestation", type=Path)

    def handle(self, *args, **options):
        try:
            path, digest, attestation = prepare_catalog(
                manifest_path=options["manifest"],
                source_root=options["source_root"],
                output_root=options["output_dir"],
                reuse_attestation_path=options["reuse_attestation"],
            )
        except (CatalogPipelineError, OSError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                f"Prepared {len(attestation['items'])} explicit items at {path}; "
                f"attestation sha256={digest}"
            )
        )
