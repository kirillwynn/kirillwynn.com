import json
from threading import Event

from apps.core.worker import ScheduledTask, WorkerScheduler


class Clock:
    value = 10.0

    def __call__(self):
        return self.value


def test_worker_once_runs_every_task_and_writes_heartbeat(tmp_path, capsys):
    called = []
    clock = Clock()
    heartbeat = tmp_path / "heartbeat.json"
    scheduler = WorkerScheduler(
        [
            ScheduledTask("first", 5, "first_command", {"limit": 1}),
            ScheduledTask("second", 7, "second_command", {}),
        ],
        heartbeat_path=heartbeat,
        clock=clock,
        wall_clock=lambda: 1234.5,
        runner=lambda command, **options: called.append((command, options)),
    )

    scheduler.run(once=True)

    assert called == [("first_command", {"limit": 1}), ("second_command", {})]
    assert json.loads(heartbeat.read_text())["timestamp"] == 1234.5
    assert '"event": "worker_stopped"' in capsys.readouterr().out


def test_task_failure_is_isolated_and_backed_off(tmp_path):
    clock = Clock()
    called = []

    def runner(command, **_options):
        called.append(command)
        if command == "broken":
            raise RuntimeError("provider secret must not be logged")

    scheduler = WorkerScheduler(
        [
            ScheduledTask("broken", 10, "broken", {}),
            ScheduledTask("healthy", 10, "healthy", {}),
        ],
        heartbeat_path=tmp_path / "heartbeat.json",
        clock=clock,
        runner=runner,
        stop_event=Event(),
    )
    scheduler.run(once=True)

    assert called == ["broken", "healthy"]
    assert scheduler.tasks[0].failures == 1
    assert scheduler.tasks[0].next_run == 30
    assert scheduler.tasks[1].failures == 0
    assert scheduler.tasks[1].next_run == 20


def test_configured_worker_tasks_are_bounded(monkeypatch):
    from apps.core.worker import configured_tasks

    monkeypatch.setenv("WORKER_EMAIL_OUTBOX_BATCH_SIZE", "7")
    monkeypatch.setenv("WORKER_EMAIL_DELIVERY_BATCH_SIZE", "9")
    monkeypatch.setenv("WORKER_AUTH_EMAIL_BATCH_SIZE", "5")

    tasks = configured_tasks()

    assert [task.command for task in tasks] == [
        "publish_scheduled_pages",
        "process_revalidation_outbox",
        "process_email_outbox",
        "process_auth_email_outbox",
        "reconcile_email_webhooks",
    ]
    assert tasks[2].options == {"limit": 7, "delivery_limit": 9}
    assert tasks[3].options == {"limit": 5}
