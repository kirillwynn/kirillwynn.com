import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "infra" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_script(name):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_manifest(path, sha, image_seed):
    payload = {
        "schema_version": 1,
        "release_sha": sha,
        "repository": "kirillwynn/kirillwynn.com",
        "built_at": "2026-07-27T00:00:00Z",
        "images": {
            "django": f"ghcr.io/kirillwynn/django@sha256:{image_seed * 64}",
            "next": f"ghcr.io/kirillwynn/next@sha256:{hex(int(image_seed, 16) + 1)[2:] * 64}",
            "edge": f"ghcr.io/kirillwynn/edge@sha256:{hex(int(image_seed, 16) + 2)[2:] * 64}",
        },
    }
    path.write_text(json.dumps(payload, sort_keys=True))
    return payload


def operation_args(
    tmp_path,
    *,
    environment="production",
    operation_id="deploy-operation-a",
    operation="deploy",
    sha="a" * 40,
    image_seed="1",
    sequence=1,
):
    manifest = tmp_path / f"{operation_id}.json"
    write_manifest(manifest, sha, image_seed)
    runtime = tmp_path / f"runtime-{operation_id}"
    runtime.mkdir(exist_ok=True)
    return SimpleNamespace(
        state_directory=tmp_path / "state",
        environment=environment,
        operation_id=operation_id,
        failed_operation_id=None,
        operation=operation,
        release_sha=sha,
        deployment_sequence=str(sequence),
        runtime_directory=runtime,
        manifest=manifest,
        phase=None,
        reason="test evidence",
        field=None,
    )


def checkpoint_args(args, phase):
    return SimpleNamespace(**{**vars(args), "phase": phase})


def advance_to_pending(module, args):
    state = module.load_state(args.state_directory, args.environment)
    attempt = state["attempts"][args.operation_id]
    for phase in module.operation_plan(attempt)[1:-1]:
        module.checkpoint(checkpoint_args(args, phase))


def activate(module, args):
    module.begin(args)
    advance_to_pending(module, args)
    module.finalize(args)
    return module.load_state(args.state_directory, args.environment)


def begin_recovery_args(base, operation_id, failed_operation_id, sequence):
    return SimpleNamespace(
        **{
            **vars(base),
            "operation_id": operation_id,
            "failed_operation_id": failed_operation_id,
            "deployment_sequence": str(sequence),
        }
    )


def state_file(args):
    return args.state_directory / args.environment / "rollout-state.json"


def test_active_a_to_b_duplicate_finalize_preserves_previous_a(tmp_path):
    module = load_script("record_rollout_state.py")
    operation_a = operation_args(tmp_path)
    activate(module, operation_a)
    operation_b = operation_args(
        tmp_path,
        operation_id="deploy-operation-b",
        sha="b" * 40,
        image_seed="4",
        sequence=2,
    )
    activate(module, operation_b)
    before = state_file(operation_b).read_bytes()
    state = module.load_state(operation_b.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == "b" * 40
    assert state["active"]["edge"]["edge_image"].endswith("6" * 64)
    assert state["previous"]["application"]["release_sha"] == "a" * 40
    assert stat.S_IMODE(state_file(operation_b).stat().st_mode) == 0o600
    assert not (state_file(operation_b).parent / "active-release.json").exists()

    module.finalize(operation_b)

    assert state_file(operation_b).read_bytes() == before
    state = module.load_state(operation_b.state_directory, "production")
    assert state["previous"]["application"]["release_sha"] == "a" * 40


FIRST_DEPLOY_TRANSITIONS = [
    "begin",
    "checkpoint-bootstrap-volume-authorized",
    "checkpoint-bootstrap-database-ready",
    "checkpoint-initial-backup-completed",
    "checkpoint-migration-started",
    "checkpoint-migration-completed",
    "checkpoint-application-healthy",
    "checkpoint-edge-healthy",
    "checkpoint-pending-public-smoke",
    "finalize",
]


@pytest.mark.parametrize("transition", FIRST_DEPLOY_TRANSITIONS)
@pytest.mark.parametrize("fault_side", ["before-replace", "after-replace"])
def test_fault_injection_each_activation_transition_is_retryable(
    monkeypatch, tmp_path, transition, fault_side
):
    module = load_script("record_rollout_state.py")
    args = operation_args(tmp_path)
    action = transition
    if transition != "begin":
        module.begin(args)
        target_phase = (
            None if transition == "finalize" else transition.removeprefix("checkpoint-")
        )
        state = module.load_state(args.state_directory, args.environment)
        for phase in module.operation_plan(state["attempts"][args.operation_id])[1:-1]:
            if phase == target_phase:
                break
            module.checkpoint(checkpoint_args(args, phase))
        if transition == "finalize":
            advance_to_pending(module, args)

    before = module.load_state(args.state_directory, args.environment)
    monkeypatch.setenv("ROLLOUT_STATE_FAULT", f"{transition}:{fault_side}")
    with pytest.raises(RuntimeError, match="injected fault"):
        if action == "begin":
            module.begin(args)
        elif action == "finalize":
            module.finalize(args)
        else:
            module.checkpoint(
                checkpoint_args(args, transition.removeprefix("checkpoint-"))
            )
    durable = module.load_state(args.state_directory, args.environment)
    expected_revision = before["revision"] + (fault_side == "after-replace")
    assert durable["revision"] == expected_revision

    monkeypatch.delenv("ROLLOUT_STATE_FAULT")
    if action == "begin":
        module.begin(args)
    elif action == "finalize":
        module.finalize(args)
    else:
        module.checkpoint(checkpoint_args(args, transition.removeprefix("checkpoint-")))
    once = state_file(args).read_bytes()
    if action == "begin":
        module.begin(args)
    elif action == "finalize":
        module.finalize(args)
    else:
        module.checkpoint(checkpoint_args(args, transition.removeprefix("checkpoint-")))
    assert state_file(args).read_bytes() == once


def test_retry_after_lost_finalize_response_is_noop(tmp_path, monkeypatch):
    module = load_script("record_rollout_state.py")
    operation_a = operation_args(tmp_path)
    activate(module, operation_a)
    operation_b = operation_args(
        tmp_path,
        operation_id="deploy-operation-b",
        sha="b" * 40,
        image_seed="4",
        sequence=2,
    )
    module.begin(operation_b)
    advance_to_pending(module, operation_b)
    monkeypatch.setenv("ROLLOUT_STATE_FAULT", "finalize:after-replace")
    with pytest.raises(RuntimeError, match="after finalize"):
        module.finalize(operation_b)
    monkeypatch.delenv("ROLLOUT_STATE_FAULT")
    durable_after_lost_response = state_file(operation_b).read_bytes()

    module.finalize(operation_b)

    assert state_file(operation_b).read_bytes() == durable_after_lost_response
    state = module.load_state(operation_b.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == "b" * 40
    assert state["previous"]["application"]["release_sha"] == "a" * 40


def test_finalize_rejects_rewritten_immutable_manifest(tmp_path):
    module = load_script("record_rollout_state.py")
    args = operation_args(tmp_path)
    module.begin(args)
    advance_to_pending(module, args)
    payload = json.loads(args.manifest.read_text())
    payload["built_at"] = "2026-07-27T00:00:01Z"
    args.manifest.write_text(json.dumps(payload, sort_keys=True))

    with pytest.raises(ValueError, match="immutable release manifest changed"):
        module.finalize(args)

    state = module.load_state(args.state_directory, "production")
    assert state["active"] is None
    assert state["attempts"][args.operation_id]["phase"] == "pending-public-smoke"


def test_logically_torn_authoritative_state_fails_closed(tmp_path):
    module = load_script("record_rollout_state.py")
    operation_a = operation_args(tmp_path)
    activate(module, operation_a)
    operation_b = operation_args(
        tmp_path,
        operation_id="deploy-operation-b",
        sha="b" * 40,
        image_seed="4",
        sequence=2,
    )
    module.begin(operation_b)
    payload = json.loads(state_file(operation_b).read_text())
    payload["active"] = payload["attempts"][operation_b.operation_id]["candidate"]
    state_file(operation_b).write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="base does not match"):
        module.load_state(operation_b.state_directory, "production")


def failed_candidate_fixture(tmp_path):
    module = load_script("record_rollout_state.py")
    operation_z = operation_args(
        tmp_path,
        operation_id="deploy-operation-z",
        sha="c" * 40,
        image_seed="7",
        sequence=1,
    )
    activate(module, operation_z)
    operation_a = operation_args(
        tmp_path,
        operation_id="deploy-operation-a",
        sha="a" * 40,
        image_seed="1",
        sequence=2,
    )
    activate(module, operation_a)
    operation_b = operation_args(
        tmp_path,
        operation_id="deploy-operation-b",
        sha="b" * 40,
        image_seed="4",
        sequence=3,
    )
    module.begin(operation_b)
    advance_to_pending(module, operation_b)
    module.fail(operation_b)
    return module, operation_z, operation_a, operation_b


def test_failed_candidate_recovery_restores_active_a_and_preserves_evidence(tmp_path):
    module, operation_z, operation_a, operation_b = failed_candidate_fixture(tmp_path)
    state = module.load_state(operation_b.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == "a" * 40
    assert state["previous"]["application"]["release_sha"] == "c" * 40
    assert state["recovery_required_for"] == operation_b.operation_id
    failure_evidence = state["attempts"][operation_b.operation_id]["evidence"].copy()

    recovery = begin_recovery_args(
        operation_a,
        "recovery-operation-a",
        operation_b.operation_id,
        4,
    )
    module.begin_recovery(recovery)
    advance_to_pending(module, recovery)
    pending = module.load_state(recovery.state_directory, "production")
    assert pending["recovery_required_for"] == operation_b.operation_id
    assert pending["attempts"][operation_b.operation_id]["evidence"] == failure_evidence
    module.finalize(recovery)
    module.finalize(recovery)

    recovered = module.load_state(recovery.state_directory, "production")
    assert recovered["active"]["application"]["release_sha"] == "a" * 40
    assert recovered["active"]["edge"]["edge_image"].endswith("3" * 64)
    assert recovered["previous"]["application"]["release_sha"] == "c" * 40
    assert recovered["recovery_required_for"] is None
    assert (
        recovered["attempts"][operation_b.operation_id]["evidence"] == failure_evidence
    )
    assert recovered["attempts"][recovery.operation_id]["status"] == "completed"


def test_normal_rollback_b_to_a_restores_application_and_edge_digest(tmp_path):
    module = load_script("record_rollout_state.py")
    operation_a = operation_args(tmp_path)
    activate(module, operation_a)
    operation_b = operation_args(
        tmp_path,
        operation_id="deploy-operation-b",
        sha="b" * 40,
        image_seed="4",
        sequence=2,
    )
    activate(module, operation_b)
    rollback = operation_args(
        tmp_path,
        operation_id="rollback-operation-a",
        operation="rollback",
        sha="a" * 40,
        image_seed="1",
        sequence=3,
    )
    rollback.manifest = operation_a.manifest
    rollback.runtime_directory = operation_a.runtime_directory
    activate(module, rollback)

    state = module.load_state(rollback.state_directory, "production")
    assert state["active"]["application"]["application_images"] == {
        "django": f"ghcr.io/kirillwynn/django@sha256:{'1' * 64}",
        "next": f"ghcr.io/kirillwynn/next@sha256:{'2' * 64}",
    }
    assert state["active"]["edge"]["edge_image"] == (
        f"ghcr.io/kirillwynn/edge@sha256:{'3' * 64}"
    )
    assert state["previous"]["application"]["release_sha"] == "b" * 40


def test_stale_duplicate_and_conflicting_operations_are_rejected(tmp_path):
    module = load_script("record_rollout_state.py")
    operation_a = operation_args(tmp_path)
    activate(module, operation_a)

    stale = operation_args(
        tmp_path,
        operation_id="deploy-operation-stale",
        sha="b" * 40,
        image_seed="4",
        sequence=1,
    )
    with pytest.raises(ValueError, match="stale or conflicts"):
        module.begin(stale)

    operation_b = operation_args(
        tmp_path,
        operation_id="deploy-operation-b",
        sha="b" * 40,
        image_seed="4",
        sequence=2,
    )
    module.begin(operation_b)
    conflict = SimpleNamespace(
        **{
            **vars(operation_b),
            "release_sha": "c" * 40,
            "manifest": tmp_path / "conflicting-operation-id.json",
        }
    )
    write_manifest(conflict.manifest, "c" * 40, "7")
    with pytest.raises(ValueError, match="conflicting immutable input"):
        module.begin(conflict)
    parallel = operation_args(
        tmp_path,
        operation_id="deploy-operation-parallel",
        sha="c" * 40,
        image_seed="7",
        sequence=3,
    )
    with pytest.raises(ValueError, match="already in progress"):
        module.begin(parallel)

    advance_to_pending(module, operation_b)
    module.finalize(operation_b)
    duplicate = operation_args(
        tmp_path,
        operation_id="deploy-operation-duplicate",
        sha="b" * 40,
        image_seed="4",
        sequence=3,
    )
    with pytest.raises(ValueError, match="different operation already activated"):
        module.begin(duplicate)


@pytest.mark.parametrize("fault_side", ["before-replace", "after-replace"])
def test_failed_and_recovery_transitions_are_fault_safe(
    tmp_path, monkeypatch, fault_side
):
    module, _, operation_a, operation_b = failed_candidate_fixture(tmp_path)
    # Re-create a pending candidate because the fixture already committed failure.
    recovery = begin_recovery_args(
        operation_a,
        "recovery-operation-a",
        operation_b.operation_id,
        4,
    )
    monkeypatch.setenv("ROLLOUT_STATE_FAULT", f"begin-recovery:{fault_side}")
    with pytest.raises(RuntimeError, match="injected fault"):
        module.begin_recovery(recovery)
    monkeypatch.delenv("ROLLOUT_STATE_FAULT")
    module.begin_recovery(recovery)
    assert (
        module.load_state(recovery.state_directory, "production")["attempts"][
            recovery.operation_id
        ]["status"]
        == "in-progress"
    )


@pytest.mark.parametrize(
    "scenario",
    [
        "pre-migration-backup",
        "recovery-backup",
        "staging-edge-candidate",
        "public-smoke-failure",
    ],
)
@pytest.mark.parametrize("fault_side", ["before-replace", "after-replace"])
def test_additional_transition_fault_matrix(
    tmp_path, monkeypatch, scenario, fault_side
):
    module = load_script("record_rollout_state.py")
    if scenario == "pre-migration-backup":
        active = operation_args(tmp_path)
        activate(module, active)
        args = operation_args(
            tmp_path,
            operation_id="deploy-operation-b",
            sha="b" * 40,
            image_seed="4",
            sequence=2,
        )
        module.begin(args)
        phase = "pre-migration-backup-completed"
        transition = f"checkpoint-{phase}"

        def action():
            module.checkpoint(checkpoint_args(args, phase))

    elif scenario == "recovery-backup":
        _, _, operation_a, operation_b = failed_candidate_fixture(tmp_path)
        args = begin_recovery_args(
            operation_a,
            "recovery-operation-a",
            operation_b.operation_id,
            4,
        )
        module.begin_recovery(args)
        phase = "recovery-backup-completed"
        transition = f"checkpoint-{phase}"

        def action():
            module.checkpoint(checkpoint_args(args, phase))

    elif scenario == "staging-edge-candidate":
        args = operation_args(tmp_path, environment="staging")
        module.begin(args)
        state = module.load_state(args.state_directory, "staging")
        for phase in module.operation_plan(state["attempts"][args.operation_id])[1:]:
            if phase == "edge-candidate-verified":
                break
            module.checkpoint(checkpoint_args(args, phase))
        transition = "checkpoint-edge-candidate-verified"

        def action():
            module.checkpoint(checkpoint_args(args, "edge-candidate-verified"))

    else:
        args = operation_args(tmp_path)
        module.begin(args)
        advance_to_pending(module, args)
        transition = "fail-public-smoke"

        def action():
            module.fail(args)

    monkeypatch.setenv("ROLLOUT_STATE_FAULT", f"{transition}:{fault_side}")
    with pytest.raises(RuntimeError, match="injected fault"):
        action()
    monkeypatch.delenv("ROLLOUT_STATE_FAULT")
    action()
    durable = state_file(args).read_bytes()
    action()
    assert state_file(args).read_bytes() == durable


@pytest.mark.parametrize("fault_side", ["before-replace", "after-replace"])
def test_reviewed_abort_transition_is_fault_safe(tmp_path, monkeypatch, fault_side):
    module = load_script("record_rollout_state.py")
    args = operation_args(tmp_path)
    module.begin(args)
    monkeypatch.setenv("ROLLOUT_STATE_FAULT", f"abort:{fault_side}")
    with pytest.raises(RuntimeError, match="injected fault"):
        module.abort(args)
    monkeypatch.delenv("ROLLOUT_STATE_FAULT")
    module.abort(args)
    state = module.load_state(args.state_directory, "production")
    assert state["attempts"][args.operation_id]["status"] == "aborted"
    assert state["active"] is None


def fake_docker(path, *, existing_volume, log_path=None):
    log_line = f"printf '%s\\n' \"$*\" >> '{log_path}'\n" if log_path else ""
    path.write_text(
        "#!/bin/sh\n"
        f"{log_line}"
        'if [ "$1 $2 $3" = "compose version --short" ]; then '
        "printf '%s\\n' 2.30.0; exit 0; fi\n"
        'if [ "$1 $2" = "volume inspect" ]; then '
        f"exit {0 if existing_volume else 1}; fi\n"
        'case "$*" in\n'
        "  *pg_dump*) printf '%s' fake-custom-dump ;;\n"
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    path.chmod(0o700)


def bootstrap_runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "control.env").write_text(
        "POSTGRES_VOLUME=kirillwynn-production-test-postgres\n"
        "POSTGRES_IMAGE=postgres@sha256:" + "9" * 64 + "\n"
    )
    (runtime / "postgres.env").write_text(
        "POSTGRES_DB=kirillwynn_production\n"
        "POSTGRES_USER=kirillwynn_production\n"
        "POSTGRES_PASSWORD=test-only\n"
    )
    return runtime


def test_existing_postgres_volume_without_bound_attempt_is_rejected(tmp_path):
    module = load_script("record_rollout_state.py")
    args = operation_args(tmp_path)
    module.begin(args)
    runtime = bootstrap_runtime(tmp_path)
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    fake_docker(binary_dir / "docker", existing_volume=True)
    result = subprocess.run(
        [
            SCRIPTS / "bootstrap_database.sh",
            "production",
            runtime,
            args.release_sha,
            args.operation_id,
            tmp_path / "backups",
        ],
        env={
            **os.environ,
            "PATH": f"{binary_dir}:{os.environ['PATH']}",
            "STATE_DIRECTORY": str(args.state_directory),
        },
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert "no durable bootstrap/rollout state" in result.stderr
    state = module.load_state(args.state_directory, "production")
    assert state["attempts"][args.operation_id]["phase"] == "attempt-recorded"


def test_interrupted_first_deploy_resumes_same_attempt_without_rebootstrap(
    tmp_path, monkeypatch
):
    module = load_script("record_rollout_state.py")
    args = operation_args(tmp_path)
    module.begin(args)
    module.checkpoint(checkpoint_args(args, "bootstrap-volume-authorized"))
    runtime = bootstrap_runtime(tmp_path)
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    fake_docker(
        binary_dir / "docker",
        existing_volume=True,
        log_path=docker_log,
    )
    environment = {
        **os.environ,
        "PATH": f"{binary_dir}:{os.environ['PATH']}",
        "STATE_DIRECTORY": str(args.state_directory),
        "ROLLOUT_STATE_FAULT": ("checkpoint-bootstrap-database-ready:after-replace"),
    }
    command = [
        SCRIPTS / "bootstrap_database.sh",
        "production",
        runtime,
        args.release_sha,
        args.operation_id,
        tmp_path / "backups",
    ]
    first = subprocess.run(command, env=environment, text=True, capture_output=True)
    assert first.returncode != 0
    environment.pop("ROLLOUT_STATE_FAULT")
    second = subprocess.run(command, env=environment, text=True, capture_output=True)
    assert second.returncode == 0, second.stderr

    state = module.load_state(args.state_directory, "production")
    attempt = state["attempts"][args.operation_id]
    assert attempt["phase"] == "initial-backup-completed"
    assert docker_log.read_text().count("up -d --wait") == 1
    metadata = next((tmp_path / "backups").rglob("*.dump.json"))
    payload = json.loads(metadata.read_text())
    assert payload["backup_kind"] == "initial-empty"
    assert payload["operation_id"] == args.operation_id
