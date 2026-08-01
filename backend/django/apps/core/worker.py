import json
import math
import os
import signal
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from threading import Event

from django.core.management import call_command


@dataclass
class ScheduledTask:
    name: str
    interval: float
    command: str
    options: dict
    next_run: float = 0
    failures: int = 0


def management_runner(command, **options):
    stdout = StringIO()
    stderr = StringIO()
    call_command(command, stdout=stdout, stderr=stderr, **options)
    return stdout.getvalue()[:2000].strip(), stderr.getvalue()[:2000].strip()


def configured_tasks() -> list[ScheduledTask]:
    def interval(name, default):
        value = float(os.environ.get(name, default))
        if not math.isfinite(value) or not 1 <= value <= 86_400:
            raise ValueError(f"{name} must be between 1 and 86400 seconds")
        return value

    def batch(name, default):
        value = int(os.environ.get(name, default))
        if not 1 <= value <= 1_000:
            raise ValueError(f"{name} must be between 1 and 1000")
        return value

    return [
        ScheduledTask(
            "scheduled-pages",
            interval("WORKER_PUBLISH_INTERVAL_SECONDS", "60"),
            "publish_scheduled_pages",
            {},
        ),
        ScheduledTask(
            "revalidation",
            interval("WORKER_REVALIDATION_INTERVAL_SECONDS", "15"),
            "process_revalidation_outbox",
            {"limit": batch("WORKER_REVALIDATION_BATCH_SIZE", "100")},
        ),
        ScheduledTask(
            "email",
            interval("WORKER_EMAIL_INTERVAL_SECONDS", "10"),
            "process_email_outbox",
            {
                "limit": batch("WORKER_EMAIL_OUTBOX_BATCH_SIZE", "25"),
                "delivery_limit": batch("WORKER_EMAIL_DELIVERY_BATCH_SIZE", "100"),
            },
        ),
        ScheduledTask(
            "auth-email",
            interval("WORKER_AUTH_EMAIL_INTERVAL_SECONDS", "10"),
            "process_auth_email_outbox",
            {"limit": batch("WORKER_AUTH_EMAIL_BATCH_SIZE", "25")},
        ),
        ScheduledTask(
            "webhooks",
            interval("WORKER_WEBHOOK_INTERVAL_SECONDS", "60"),
            "reconcile_email_webhooks",
            {"limit": batch("WORKER_WEBHOOK_BATCH_SIZE", "100")},
        ),
    ]


class WorkerScheduler:
    def __init__(
        self,
        tasks: list[ScheduledTask],
        *,
        heartbeat_path: Path,
        stop_event: Event | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        runner: Callable[..., object] = management_runner,
        wait: Callable[[float], bool] | None = None,
        max_backoff: float = 300,
    ):
        if not tasks or any(
            not math.isfinite(task.interval) or task.interval <= 0 for task in tasks
        ):
            raise ValueError("worker tasks require positive intervals")
        self.tasks = tasks
        self.heartbeat_path = heartbeat_path
        self.stop_event = stop_event or Event()
        self.clock = clock
        self.wall_clock = wall_clock
        self.runner = runner
        self.wait = wait or self.stop_event.wait
        self.max_backoff = max_backoff

    def log(self, event: str, *, error: bool = False, **fields):
        stream = sys.stderr if error else sys.stdout
        print(json.dumps({"event": event, **fields}, sort_keys=True), file=stream, flush=True)

    def heartbeat(self):
        self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"pid": os.getpid(), "timestamp": self.wall_clock()},
            sort_keys=True,
        )
        descriptor, temporary = tempfile.mkstemp(
            dir=self.heartbeat_path.parent,
            prefix=f".{self.heartbeat_path.name}.",
        )
        try:
            with os.fdopen(descriptor, "w") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.heartbeat_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def run_task(self, task: ScheduledTask):
        started = self.clock()
        try:
            output = self.runner(task.command, **task.options)
        except Exception as error:
            task.failures += 1
            backoff = min(task.interval * (2 ** min(task.failures, 6)), self.max_backoff)
            task.next_run = self.clock() + backoff
            self.log(
                "task_failed",
                error=True,
                task=task.name,
                error_type=type(error).__name__,
                failures=task.failures,
                retry_in_seconds=backoff,
            )
        else:
            task.failures = 0
            task.next_run = self.clock() + task.interval
            self.log(
                "task_completed",
                task=task.name,
                duration_seconds=round(self.clock() - started, 3),
            )
            if isinstance(output, tuple):
                stdout, stderr = output
                if stdout:
                    self.log("task_output", task=task.name, stream="stdout", message=stdout)
                if stderr:
                    self.log(
                        "task_output",
                        error=True,
                        task=task.name,
                        stream="stderr",
                        message=stderr,
                    )
        self.heartbeat()

    def run(self, *, once: bool = False):
        now = self.clock()
        for task in self.tasks:
            task.next_run = now
        self.heartbeat()
        self.log("worker_started", tasks=[task.name for task in self.tasks])
        while not self.stop_event.is_set():
            now = self.clock()
            due = [task for task in self.tasks if task.next_run <= now]
            for task in due:
                if self.stop_event.is_set():
                    break
                self.run_task(task)
            if once:
                break
            next_run = min(task.next_run for task in self.tasks)
            self.wait(max(0.1, min(next_run - self.clock(), 5)))
            self.heartbeat()
        self.log("worker_stopped")


def install_signal_handlers(stop_event: Event):
    def stop(signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
