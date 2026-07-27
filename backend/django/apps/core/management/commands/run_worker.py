from pathlib import Path
from threading import Event

from django.core.management.base import BaseCommand

from apps.core.worker import WorkerScheduler, configured_tasks, install_signal_handlers


class Command(BaseCommand):
    help = "Run the bounded database-outbox and Wagtail scheduling worker."

    def add_arguments(self, parser):
        parser.add_argument(
            "--heartbeat-file",
            default="/tmp/kirillwynn-worker/heartbeat.json",
        )
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        stop_event = Event()
        install_signal_handlers(stop_event)
        WorkerScheduler(
            configured_tasks(),
            heartbeat_path=Path(options["heartbeat_file"]),
            stop_event=stop_event,
        ).run(once=options["once"])
