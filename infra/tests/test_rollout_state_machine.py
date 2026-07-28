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
        postgres_volume=f"kirillwynn-{environment}-test-postgres",
        postgres_image="postgres@sha256:" + "9" * 64,
        resolution=None,
        category="public-smoke",
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


def begin_resolution_args(
    base,
    operation_id,
    failed_operation_id,
    sequence,
    resolution,
):
    return SimpleNamespace(
        **{
            **vars(base),
            "operation_id": operation_id,
            "failed_operation_id": failed_operation_id,
            "deployment_sequence": str(sequence),
            "resolution": resolution,
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
    "checkpoint-initial-backup-started",
    "checkpoint-initial-backup-completed",
    "checkpoint-migration-started",
    "checkpoint-migration-completed",
    "checkpoint-application-rollout-started",
    "checkpoint-application-healthy",
    "checkpoint-edge-rollout-started",
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


def test_logically_torn_resolution_ownership_fails_closed(tmp_path):
    module, _, operation_a, operation_b = failed_candidate_fixture(tmp_path)
    recovery = begin_recovery_args(
        operation_a,
        "recovery-operation-a",
        operation_b.operation_id,
        4,
    )
    module.begin_recovery(recovery)
    payload = json.loads(state_file(recovery).read_text())
    payload["attempts"][operation_b.operation_id]["failure"]["resolution"][
        "operation_id"
    ] = "foreign-resolution-operation"
    state_file(recovery).write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="invalid resolution ownership"):
        module.load_state(recovery.state_directory, "production")


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


def failed_recovery_fixture(tmp_path):
    module, operation_z, operation_a, operation_b = failed_candidate_fixture(tmp_path)
    recovery = begin_recovery_args(
        operation_a,
        "recovery-operation-a",
        operation_b.operation_id,
        4,
    )
    module.begin_recovery(recovery)
    advance_to_pending(module, recovery)
    module.fail(recovery)
    return module, operation_z, operation_a, operation_b, recovery


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
    module.begin_recovery(recovery)

    recovered = module.load_state(recovery.state_directory, "production")
    assert recovered["active"]["application"]["release_sha"] == "a" * 40
    assert recovered["active"]["edge"]["edge_image"].endswith("3" * 64)
    assert recovered["previous"]["application"]["release_sha"] == "c" * 40
    assert recovered["recovery_required_for"] is None
    assert (
        recovered["attempts"][operation_b.operation_id]["evidence"] == failure_evidence
    )
    assert (
        recovered["attempts"][operation_b.operation_id]["failure"]["resolution"]["kind"]
        == "recovery"
    )
    assert (
        recovered["attempts"][operation_b.operation_id]["failure"]["resolution"][
            "status"
        ]
        == "completed"
    )
    assert recovered["attempts"][recovery.operation_id]["status"] == "completed"


@pytest.mark.parametrize("failed_retry_count", [0, 2])
def test_retry_recovery_inherits_preserve_previous_recursively(
    tmp_path, failed_retry_count
):
    module, operation_z, operation_a, _, failed = failed_recovery_fixture(tmp_path)
    sequence = 5
    for retry_number in range(failed_retry_count):
        retry = begin_resolution_args(
            operation_a,
            f"retry-recovery-failed-{retry_number}",
            failed.operation_id,
            sequence,
            "retry",
        )
        module.begin_resolution(retry)
        advance_to_pending(module, retry)
        module.fail(retry)
        failed = retry
        sequence += 1

    retry = begin_resolution_args(
        operation_a,
        "retry-recovery-success",
        failed.operation_id,
        sequence,
        "retry",
    )
    module.begin_resolution(retry)
    state = module.load_state(retry.state_directory, "production")
    assert (
        state["attempts"][retry.operation_id]["activation_policy"]
        == "preserve-previous"
    )
    advance_to_pending(module, retry)
    module.finalize(retry)
    finalized = state_file(retry).read_bytes()
    module.finalize(retry)

    assert state_file(retry).read_bytes() == finalized
    state = module.load_state(retry.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == operation_a.release_sha
    assert state["previous"]["application"]["release_sha"] == operation_z.release_sha
    assert (
        state["active"]["application"] != state["previous"]["application"]
        or state["active"]["edge"] != state["previous"]["edge"]
    )


def test_failed_recovery_followed_by_new_recovery_preserves_previous_z(tmp_path):
    module, operation_z, operation_a, _, failed_recovery = failed_recovery_fixture(
        tmp_path
    )
    recovery = begin_recovery_args(
        operation_a,
        "recovery-operation-a-second",
        failed_recovery.operation_id,
        5,
    )
    module.begin_recovery(recovery)
    advance_to_pending(module, recovery)
    module.finalize(recovery)

    state = module.load_state(recovery.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == operation_a.release_sha
    assert state["previous"]["application"]["release_sha"] == operation_z.release_sha
    assert (
        state["attempts"][recovery.operation_id]["activation_policy"]
        == "preserve-previous"
    )


def test_failed_recovery_fix_forward_rotates_active_a_to_previous(tmp_path):
    module, _, operation_a, _, failed_recovery = failed_recovery_fixture(tmp_path)
    candidate_c = operation_args(
        tmp_path,
        operation_id="fix-forward-operation-c",
        sha="d" * 40,
        image_seed="a",
        sequence=5,
    )
    fix_forward = begin_resolution_args(
        candidate_c,
        candidate_c.operation_id,
        failed_recovery.operation_id,
        5,
        "fix-forward",
    )
    module.begin_resolution(fix_forward)
    advance_to_pending(module, fix_forward)
    module.finalize(fix_forward)

    state = module.load_state(fix_forward.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == candidate_c.release_sha
    assert state["previous"]["application"]["release_sha"] == operation_a.release_sha
    assert (
        state["attempts"][fix_forward.operation_id]["activation_policy"]
        == "rotate-active-to-previous"
    )


def test_failed_rollback_retry_rotates_active_b_to_previous(tmp_path):
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
        sha=operation_a.release_sha,
        image_seed="1",
        sequence=3,
    )
    rollback.manifest = operation_a.manifest
    rollback.runtime_directory = operation_a.runtime_directory
    module.begin(rollback)
    advance_to_pending(module, rollback)
    module.fail(rollback)

    retry = begin_resolution_args(
        operation_a,
        "retry-rollback-operation-a",
        rollback.operation_id,
        4,
        "retry",
    )
    module.begin_resolution(retry)
    advance_to_pending(module, retry)
    module.finalize(retry)

    state = module.load_state(retry.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == operation_a.release_sha
    assert state["previous"]["application"]["release_sha"] == operation_b.release_sha
    assert (
        state["attempts"][retry.operation_id]["activation_policy"]
        == "rotate-active-to-previous"
    )


def test_torn_retry_activation_policy_lineage_fails_deep_validation(tmp_path):
    module, _, operation_a, _, failed_recovery = failed_recovery_fixture(tmp_path)
    retry = begin_resolution_args(
        operation_a,
        "retry-recovery-operation-a",
        failed_recovery.operation_id,
        5,
        "retry",
    )
    module.begin_resolution(retry)
    payload = json.loads(state_file(retry).read_text())
    payload["attempts"][retry.operation_id]["activation_policy"] = (
        "rotate-active-to-previous"
    )
    state_file(retry).write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="activation policy conflicts"):
        module.load_state(retry.state_directory, "production")


@pytest.mark.parametrize(
    "failed_phase",
    [
        "pre-migration-backup-started",
        "pre-migration-backup-completed",
        "migration-started",
        "migration-completed",
        "application-rollout-started",
        "application-healthy",
        "edge-rollout-started",
        "edge-healthy",
        "pending-public-smoke",
    ],
)
def test_active_a_internal_failure_recovery_repeats_all_runtime_gates(
    tmp_path, failed_phase
):
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
    state = module.load_state(operation_b.state_directory, "production")
    for phase in module.operation_plan(state["attempts"][operation_b.operation_id])[1:]:
        module.checkpoint(checkpoint_args(operation_b, phase))
        if phase == failed_phase:
            break
    module.fail(operation_b)

    recovery = begin_recovery_args(
        operation_a,
        "recovery-operation-a",
        operation_b.operation_id,
        3,
    )
    module.begin_recovery(recovery)
    state = module.load_state(recovery.state_directory, "production")
    assert module.operation_plan(state["attempts"][recovery.operation_id]) == [
        "attempt-recorded",
        "recovery-backup-started",
        "recovery-backup-completed",
        "application-rollout-started",
        "application-healthy",
        "edge-rollout-started",
        "edge-healthy",
        "pending-public-smoke",
        "complete",
    ]
    advance_to_pending(module, recovery)
    module.finalize(recovery)
    state = module.load_state(recovery.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == "a" * 40
    assert state["active"]["edge"]["edge_image"].endswith("3" * 64)


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
        module.checkpoint(checkpoint_args(args, "pre-migration-backup-started"))
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
        module.checkpoint(checkpoint_args(args, "recovery-backup-started"))
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
        transition = "fail"

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


FIRST_DEPLOY_MUTATION_PHASES = [
    "bootstrap-volume-authorized",
    "bootstrap-database-ready",
    "initial-backup-started",
    "initial-backup-completed",
    "migration-started",
    "migration-completed",
    "application-rollout-started",
    "application-healthy",
    "edge-rollout-started",
    "edge-healthy",
    "pending-public-smoke",
]


@pytest.mark.parametrize("failed_phase", FIRST_DEPLOY_MUTATION_PHASES)
@pytest.mark.parametrize("fault_side", ["before-replace", "after-replace"])
def test_first_deploy_failure_is_durable_review_required_and_idempotent(
    tmp_path, monkeypatch, failed_phase, fault_side
):
    module = load_script("record_rollout_state.py")
    args = operation_args(tmp_path)
    module.begin(args)
    state = module.load_state(args.state_directory, args.environment)
    for phase in module.operation_plan(state["attempts"][args.operation_id])[1:]:
        module.checkpoint(checkpoint_args(args, phase))
        if phase == failed_phase:
            break

    monkeypatch.setenv("ROLLOUT_STATE_FAULT", f"fail:{fault_side}")
    with pytest.raises(RuntimeError, match="injected fault"):
        module.fail(args)
    monkeypatch.delenv("ROLLOUT_STATE_FAULT")
    module.fail(args)
    once = state_file(args).read_bytes()
    module.fail(args)
    assert state_file(args).read_bytes() == once

    state = module.load_state(args.state_directory, "production")
    attempt = state["attempts"][args.operation_id]
    failure = attempt["failure"]
    assert attempt["status"] == "failed"
    assert failure["failed_at_phase"] == failed_phase
    assert failure["category"] == "public-smoke"
    assert failure["candidate"] == attempt["candidate"]
    assert failure["base_active"] is None
    assert failure["base_database"]["lifecycle_state"] == "absent"
    assert failure["database_at_failure"]["environment"] == "production"
    assert failure["possible_side_effects"]
    assert state["in_progress_operation_id"] is None
    assert state["recovery_required_for"] == args.operation_id

    conflict = SimpleNamespace(**{**vars(args), "reason": "different evidence"})
    with pytest.raises(ValueError, match="conflicting failure"):
        module.fail(conflict)
    ordinary = operation_args(
        tmp_path,
        operation_id="deploy-operation-c",
        sha="c" * 40,
        image_seed="7",
        sequence=2,
    )
    with pytest.raises(ValueError, match="reviewed recovery"):
        module.begin(ordinary)


def failed_first_candidate(module, tmp_path):
    failed = operation_args(tmp_path, operation_id="deploy-operation-b")
    module.begin(failed)
    advance_to_pending(module, failed)
    module.fail(failed)
    return failed


def test_failed_first_deploy_retry_same_candidate_succeeds_idempotently(tmp_path):
    module = load_script("record_rollout_state.py")
    failed = failed_first_candidate(module, tmp_path)
    retry = begin_resolution_args(
        failed,
        "retry-operation-b",
        failed.operation_id,
        2,
        "retry",
    )
    module.begin_resolution(retry)
    module.begin_resolution(retry)
    state = module.load_state(retry.state_directory, "production")
    plan = module.operation_plan(state["attempts"][retry.operation_id])
    assert "recovery-backup-completed" in plan
    assert "initial-backup-completed" not in plan
    advance_to_pending(module, retry)
    module.finalize(retry)
    before = state_file(retry).read_bytes()
    module.finalize(retry)
    module.begin_resolution(retry)
    assert state_file(retry).read_bytes() == before

    state = module.load_state(retry.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == "a" * 40
    assert state["previous"] is None
    assert state["database"]["lifecycle_state"] == "migrated"
    assert state["database"]["last_backup"]["purpose"] == "recovery"
    assert state["recovery_required_for"] is None
    resolution = state["attempts"][failed.operation_id]["failure"]["resolution"]
    assert resolution["kind"] == "retry"
    assert resolution["status"] == "completed"


def test_resolve_shell_uses_reviewed_sequence_without_rewriting_failed_runtime(
    tmp_path,
):
    module, operation_z, _, operation_b = failed_candidate_fixture(tmp_path)
    manifest = json.loads(operation_b.manifest.read_text())
    control_env = operation_b.runtime_directory / "control.env"
    control_env.write_text(
        f"RELEASE_SHA={operation_b.release_sha}\n"
        "DEPLOY_SEQUENCE=3\n"
        "POSTGRES_VOLUME=kirillwynn-production-test-postgres\n"
        f"POSTGRES_IMAGE={operation_b.postgres_image}\n"
        f"DJANGO_IMAGE={manifest['images']['django']}\n"
        f"NEXT_IMAGE={manifest['images']['next']}\n"
    )
    (operation_b.runtime_directory / "postgres.env").write_text(
        "POSTGRES_DB=kirillwynn_production\n"
        "POSTGRES_USER=kirillwynn_production\n"
        "POSTGRES_PASSWORD=test-only\n"
    )
    edge_env = tmp_path / "edge.env"
    edge_env.write_text("EDGE_TEST_ONLY=1\n")
    runtime_before = {
        path.relative_to(operation_b.runtime_directory): path.read_bytes()
        for path in operation_b.runtime_directory.rglob("*")
        if path.is_file()
    }
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    fake_docker(
        binary_dir / "docker",
        existing_volume=True,
        operation_id=operation_z.operation_id,
        application_images={
            "django": manifest["images"]["django"],
            "next": manifest["images"]["next"],
        },
        edge_image=manifest["images"]["edge"],
    )
    environment = {
        **os.environ,
        "PATH": f"{binary_dir}:{os.environ['PATH']}",
        "STATE_DIRECTORY": str(operation_b.state_directory),
        "BACKUP_DIRECTORY": str(tmp_path / "backups"),
    }
    base_command = [
        SCRIPTS / "resolve_failed_rollout.sh",
        "production",
        operation_b.operation_id,
        "retry-operation-b-shell",
    ]

    stale = subprocess.run(
        [
            *base_command,
            "3",
            "retry",
            operation_b.runtime_directory,
            operation_b.manifest,
            edge_env,
        ],
        env=environment,
        text=True,
        capture_output=True,
    )
    assert stale.returncode != 0
    assert "must advance failed operation" in stale.stderr

    accepted = subprocess.run(
        [
            *base_command,
            "4",
            "retry",
            operation_b.runtime_directory,
            operation_b.manifest,
            edge_env,
        ],
        env=environment,
        text=True,
        capture_output=True,
    )
    assert accepted.returncode == 0, accepted.stderr
    state = module.load_state(operation_b.state_directory, "production")
    attempt = state["attempts"]["retry-operation-b-shell"]
    assert attempt["deployment_sequence"] == 4
    assert attempt["phase"] == "pending-public-smoke"
    assert (
        attempt["candidate"]["application"]
        == state["attempts"][operation_b.operation_id]["candidate"]["application"]
    )
    accepted_state = state_file(operation_b).read_bytes()

    duplicate = subprocess.run(
        [
            *base_command,
            "4",
            "retry",
            operation_b.runtime_directory,
            operation_b.manifest,
            edge_env,
        ],
        env=environment,
        text=True,
        capture_output=True,
    )
    assert duplicate.returncode == 0, duplicate.stderr
    assert state_file(operation_b).read_bytes() == accepted_state

    conflict = subprocess.run(
        [
            *base_command,
            "5",
            "retry",
            operation_b.runtime_directory,
            operation_b.manifest,
            edge_env,
        ],
        env=environment,
        text=True,
        capture_output=True,
    )
    assert conflict.returncode != 0
    assert "conflicting immutable input" in conflict.stderr
    assert state_file(operation_b).read_bytes() == accepted_state
    runtime_after = {
        path.relative_to(operation_b.runtime_directory): path.read_bytes()
        for path in operation_b.runtime_directory.rglob("*")
        if path.is_file()
    }
    assert runtime_after == runtime_before


def test_failed_first_deploy_fix_forward_to_new_release_uses_owned_database(
    tmp_path,
):
    module = load_script("record_rollout_state.py")
    failed = failed_first_candidate(module, tmp_path)
    candidate_c = operation_args(
        tmp_path,
        operation_id="fix-forward-operation-c",
        sha="c" * 40,
        image_seed="7",
        sequence=2,
    )
    fix_forward = begin_resolution_args(
        candidate_c,
        candidate_c.operation_id,
        failed.operation_id,
        2,
        "fix-forward",
    )
    module.begin_resolution(fix_forward)
    module.begin_resolution(fix_forward)
    state = module.load_state(fix_forward.state_directory, "production")
    plan = module.operation_plan(state["attempts"][fix_forward.operation_id])
    assert "recovery-backup-completed" in plan
    assert "initial-backup-completed" not in plan
    advance_to_pending(module, fix_forward)
    module.finalize(fix_forward)
    module.finalize(fix_forward)
    before = state_file(fix_forward).read_bytes()
    module.begin_resolution(fix_forward)
    assert state_file(fix_forward).read_bytes() == before

    state = module.load_state(fix_forward.state_directory, "production")
    assert state["active"]["application"]["release_sha"] == "c" * 40
    assert state["database"]["bootstrap_operation_id"] == failed.operation_id
    assert state["database"]["initial_backup"]["operation_id"] == failed.operation_id
    assert (
        state["database"]["last_migration"]["operation_id"] == fix_forward.operation_id
    )
    assert state["database"]["last_backup"]["purpose"] == "recovery"


def test_failed_first_authorization_can_transfer_to_reviewed_retry(tmp_path):
    module = load_script("record_rollout_state.py")
    failed = operation_args(tmp_path)
    module.begin(failed)
    module.checkpoint(checkpoint_args(failed, "bootstrap-volume-authorized"))
    module.fail(failed)
    retry = begin_resolution_args(
        failed,
        "retry-operation-a",
        failed.operation_id,
        2,
        "retry",
    )
    module.begin_resolution(retry)
    state = module.load_state(retry.state_directory, "production")
    plan = module.operation_plan(state["attempts"][retry.operation_id])
    assert plan[1:4] == [
        "bootstrap-database-ready",
        "initial-backup-started",
        "initial-backup-completed",
    ]
    advance_to_pending(module, retry)
    module.finalize(retry)
    state = module.load_state(retry.state_directory, "production")
    assert state["database"]["bootstrap_operation_id"] == failed.operation_id
    assert state["active"]["application"]["release_sha"] == failed.release_sha


def test_pre_mutation_remote_failure_has_reviewed_retry_path(tmp_path):
    module = load_script("record_rollout_state.py")
    failed = operation_args(tmp_path)
    module.begin(failed)
    failure = SimpleNamespace(
        **{
            **vars(failed),
            "category": "remote-rollout",
            "reason": "remote rollout command failed",
        }
    )
    module.fail(failure)
    retry = begin_resolution_args(
        failed,
        "retry-operation-a",
        failed.operation_id,
        2,
        "retry",
    )
    module.begin_resolution(retry)
    state = module.load_state(retry.state_directory, "production")
    plan = module.operation_plan(state["attempts"][retry.operation_id])
    assert plan[1:5] == [
        "bootstrap-volume-authorized",
        "bootstrap-database-ready",
        "initial-backup-started",
        "initial-backup-completed",
    ]


def fake_docker(
    path,
    *,
    existing_volume,
    log_path=None,
    environment="production",
    operation_id="deploy-operation-a",
    volume_name="kirillwynn-production-test-postgres",
    matching_labels=True,
    application_images=None,
    edge_image=None,
):
    log_line = f"printf '%s\\n' \"$*\" >> '{log_path}'\n" if log_path else ""
    marker = path.with_suffix(".volume")
    if existing_volume:
        marker.touch()
    label_environment = environment if matching_labels else "foreign"
    label_operation = operation_id if matching_labels else "foreign-operation"
    label_volume = volume_name if matching_labels else "foreign-volume"
    container_commands = ""
    if application_images is not None and edge_image is not None:
        container_commands = (
            'case "$*" in\n'
            '  *" ps -q django") printf "%s\\n" "django-container" ;;\n'
            '  *" ps -q worker") printf "%s\\n" "worker-container" ;;\n'
            '  *" ps -q next") printf "%s\\n" "next-container" ;;\n'
            '  *" ps -q edge") printf "%s\\n" "edge-container" ;;\n'
            "esac\n"
            'if [ "$1" = "inspect" ]; then\n'
            '  case "$*" in\n'
            f'    *django-container) printf "%s\\n" "{application_images["django"]}" ;;\n'
            f'    *worker-container) printf "%s\\n" "{application_images["django"]}" ;;\n'
            f'    *next-container) printf "%s\\n" "{application_images["next"]}" ;;\n'
            f'    *edge-container) printf "%s\\n" "{edge_image}" ;;\n'
            "  esac\n"
            "  exit 0\n"
            "fi\n"
        )
    path.write_text(
        "#!/bin/sh\n"
        f"{log_line}"
        'if [ "$1 $2 $3" = "compose version --short" ]; then '
        "printf '%s\\n' 2.30.0; exit 0; fi\n"
        'if [ "$1 $2" = "volume inspect" ]; then\n'
        f"  test -e '{marker}' || exit 1\n"
        '  case "$*" in\n'
        f'    *com.kirillwynn.environment*) printf "%s\\n" "{label_environment}" ;;\n'
        '    *com.kirillwynn.role*) printf "%s\\n" "postgres-data" ;;\n'
        f'    *com.kirillwynn.bootstrap-operation-id*) printf "%s\\n" "{label_operation}" ;;\n'
        f'    *com.kirillwynn.volume-name*) printf "%s\\n" "{label_volume}" ;;\n'
        "  esac\n"
        "  exit 0\n"
        "fi\n"
        'if [ "$1 $2" = "volume create" ]; then\n'
        f"  : > '{marker}'\n"
        "  exit 0\n"
        "fi\n"
        f"{container_commands}"
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
        operation_id=args.operation_id,
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


@pytest.mark.parametrize(
    ("fault", "expected_up_calls"),
    [
        ("after-volume-authorization", 1),
        ("after-volume-create", 1),
        ("after-container-start", 2),
    ],
)
def test_bootstrap_crash_gaps_resume_with_one_matching_owned_volume(
    tmp_path, fault, expected_up_calls
):
    module = load_script("record_rollout_state.py")
    args = operation_args(tmp_path)
    module.begin(args)
    runtime = bootstrap_runtime(tmp_path)
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    fake_docker(
        binary_dir / "docker",
        existing_volume=False,
        log_path=docker_log,
        operation_id=args.operation_id,
    )
    environment = {
        **os.environ,
        "PATH": f"{binary_dir}:{os.environ['PATH']}",
        "STATE_DIRECTORY": str(args.state_directory),
        "BOOTSTRAP_DATABASE_FAULT": fault,
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
    assert first.returncode == 97
    environment.pop("BOOTSTRAP_DATABASE_FAULT")
    second = subprocess.run(command, env=environment, text=True, capture_output=True)
    assert second.returncode == 0, second.stderr

    log = docker_log.read_text()
    assert log.count("volume create") == 1
    assert log.count("up -d --wait") == expected_up_calls
    for label in (
        "com.kirillwynn.environment=production",
        "com.kirillwynn.role=postgres-data",
        f"com.kirillwynn.bootstrap-operation-id={args.operation_id}",
        "com.kirillwynn.volume-name=kirillwynn-production-test-postgres",
    ):
        assert label in log
    state = module.load_state(args.state_directory, "production")
    assert state["database"]["lifecycle_state"] == "ready"
    assert state["database"]["bootstrap_operation_id"] == args.operation_id
    assert state["attempts"][args.operation_id]["phase"] == "initial-backup-completed"


def test_authorized_foreign_volume_is_rejected_without_starting_postgres(tmp_path):
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
        operation_id=args.operation_id,
        matching_labels=False,
    )
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
    assert "ownership labels do not match" in result.stderr
    assert "up -d --wait" not in docker_log.read_text()


def test_confirmed_database_ready_volume_disappearance_fails_closed(tmp_path):
    module = load_script("record_rollout_state.py")
    args = operation_args(tmp_path)
    module.begin(args)
    module.checkpoint(checkpoint_args(args, "bootstrap-volume-authorized"))
    module.checkpoint(checkpoint_args(args, "bootstrap-database-ready"))
    runtime = bootstrap_runtime(tmp_path)
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    fake_docker(
        binary_dir / "docker",
        existing_volume=False,
        operation_id=args.operation_id,
    )
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
    assert "database-ready PostgreSQL volume disappeared" in result.stderr
