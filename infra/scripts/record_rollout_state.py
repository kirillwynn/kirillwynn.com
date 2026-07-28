#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from validate_release_manifest import load_manifest

SCHEMA_VERSION = 2
OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
CHECKSUM = re.compile(r"^[0-9a-f]{64}$")
LEGACY_STATE_FILES = {
    "active-release.json",
    "current-manifest.json",
    "previous-manifest.json",
}
REFERENCE_FIELDS = {
    "release_sha",
    "manifest_path",
    "manifest_sha256",
    "runtime_directory",
    "application_images",
    "edge_image",
}
SNAPSHOT_FIELDS = {
    "application",
    "edge",
    "deployment_sequence",
    "activated_by_operation_id",
}
ATTEMPT_FIELDS = {
    "operation_id",
    "kind",
    "environment",
    "status",
    "phase",
    "phase_history",
    "deployment_sequence",
    "candidate",
    "base_active",
    "base_previous",
    "first_deploy",
    "recovers_operation_id",
    "created_at",
    "updated_at",
    "evidence",
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ensure_directory(path):
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    if not existed:
        fsync_directory(path)
        fsync_directory(path.parent)


def atomic_json(path, payload, transition):
    ensure_directory(path.parent)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if os.environ.get("ROLLOUT_STATE_FAULT") == f"{transition}:before-replace":
            raise RuntimeError(f"injected fault before {transition} replace")
        os.replace(temporary, path)
        fsync_directory(path.parent)
        if os.environ.get("ROLLOUT_STATE_FAULT") == f"{transition}:after-replace":
            raise RuntimeError(f"injected fault after {transition} replace")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def state_path(state_directory, environment):
    return state_directory / environment / "rollout-state.json"


def empty_state(environment):
    return {
        "schema_version": SCHEMA_VERSION,
        "environment": environment,
        "revision": 0,
        "active": None,
        "previous": None,
        "in_progress_operation_id": None,
        "recovery_required_for": None,
        "attempts": {},
    }


def validate_reference_shape(reference):
    if (
        not isinstance(reference, dict)
        or set(reference) != REFERENCE_FIELDS
        or not SHA.fullmatch(reference.get("release_sha", ""))
        or not CHECKSUM.fullmatch(reference.get("manifest_sha256", ""))
        or not isinstance(reference.get("manifest_path"), str)
        or not Path(reference["manifest_path"]).is_absolute()
        or not isinstance(reference.get("runtime_directory"), str)
        or not Path(reference["runtime_directory"]).is_absolute()
        or set(reference.get("application_images", {})) != {"django", "next"}
        or not all(
            isinstance(image, str)
            for image in (
                *reference["application_images"].values(),
                reference.get("edge_image"),
            )
        )
    ):
        raise ValueError("authoritative rollout state has an invalid release reference")


def validate_snapshot_shape(snapshot, environment):
    if not isinstance(snapshot, dict) or set(snapshot) != SNAPSHOT_FIELDS:
        raise ValueError(
            "authoritative rollout state has an invalid component snapshot"
        )
    validate_reference_shape(snapshot["application"])
    if environment == "production":
        validate_reference_shape(snapshot["edge"])
    elif snapshot["edge"] is not None:
        validate_reference_shape(snapshot["edge"])
    if (
        not isinstance(snapshot["deployment_sequence"], int)
        or snapshot["deployment_sequence"] < 1
        or not OPERATION_ID.fullmatch(snapshot["activated_by_operation_id"])
    ):
        raise ValueError("authoritative rollout state snapshot identity is invalid")


def validate_attempt_shape(operation_id, attempt, environment):
    if (
        not OPERATION_ID.fullmatch(operation_id)
        or not isinstance(attempt, dict)
        or set(attempt) != ATTEMPT_FIELDS
        or attempt["operation_id"] != operation_id
        or attempt["environment"] != environment
        or attempt["kind"] not in {"deploy", "rollback", "recovery"}
        or attempt["status"] not in {"in-progress", "completed", "failed", "aborted"}
        or not isinstance(attempt["deployment_sequence"], int)
        or attempt["deployment_sequence"] < 1
        or not isinstance(attempt["first_deploy"], bool)
        or not isinstance(attempt["phase_history"], list)
        or not attempt["phase_history"]
        or attempt["phase_history"][-1] != attempt["phase"]
        or not isinstance(attempt["evidence"], list)
        or not isinstance(attempt["created_at"], str)
        or not isinstance(attempt["updated_at"], str)
    ):
        raise ValueError("authoritative rollout state has an invalid attempt")
    validate_snapshot_shape(attempt["candidate"], environment)
    for snapshot in (attempt["base_active"], attempt["base_previous"]):
        if snapshot is not None:
            validate_snapshot_shape(snapshot, environment)
    recovery_id = attempt["recovers_operation_id"]
    if attempt["kind"] == "recovery":
        if not isinstance(recovery_id, str) or not OPERATION_ID.fullmatch(recovery_id):
            raise ValueError("recovery attempt does not identify failed evidence")
    elif recovery_id is not None:
        raise ValueError("non-recovery attempt contains a recovery target")
    expected_terminal = {
        "completed": "complete",
        "failed": "failed-public-smoke",
        "aborted": "aborted",
    }
    if attempt["status"] in expected_terminal:
        if attempt["phase"] != expected_terminal[attempt["status"]]:
            raise ValueError("attempt status and terminal phase disagree")
    elif attempt["phase"] not in operation_plan(attempt)[:-1]:
        raise ValueError("in-progress attempt phase is invalid")


def validate_state_shape(state, environment):
    if (
        set(state)
        != {
            "schema_version",
            "environment",
            "revision",
            "active",
            "previous",
            "in_progress_operation_id",
            "recovery_required_for",
            "attempts",
        }
        or state["schema_version"] != SCHEMA_VERSION
        or state["environment"] != environment
        or not isinstance(state["revision"], int)
        or state["revision"] < 0
        or not isinstance(state["attempts"], dict)
    ):
        raise ValueError("authoritative rollout state is invalid")
    for snapshot in (state["active"], state["previous"]):
        if snapshot is not None:
            validate_snapshot_shape(snapshot, environment)
    for operation_id, attempt in state["attempts"].items():
        validate_attempt_shape(operation_id, attempt, environment)


def load_state(state_directory, environment):
    path = state_path(state_directory, environment)
    if not path.exists():
        environment_dir = path.parent
        if environment_dir.exists() and any(
            (environment_dir / name).exists() for name in LEGACY_STATE_FILES
        ):
            raise ValueError(
                "legacy rollout state requires an explicit reviewed state migration"
            )
        return empty_state(environment)
    state = json.loads(path.read_text())
    validate_state_shape(state, environment)
    current = state["in_progress_operation_id"]
    if current is not None:
        attempt = state["attempts"].get(current)
        if not attempt or attempt.get("status") != "in-progress":
            raise ValueError(
                "authoritative rollout state has an invalid operation pointer"
            )
        if attempt["base_active"] != state["active"]:
            raise ValueError(
                "in-progress operation base does not match authoritative active state"
            )
    recovery = state["recovery_required_for"]
    if recovery is not None:
        attempt = state["attempts"].get(recovery)
        if not attempt or attempt.get("status") != "failed":
            raise ValueError(
                "authoritative rollout state has invalid recovery evidence"
            )
    return state


def save_state(args, state, transition):
    state["revision"] += 1
    atomic_json(
        state_path(args.state_directory, args.environment),
        state,
        transition,
    )


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_reference(manifest_path, runtime_directory):
    manifest_path = manifest_path.resolve()
    runtime_directory = runtime_directory.resolve()
    manifest = load_manifest(manifest_path)
    return {
        "release_sha": manifest["release_sha"],
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "runtime_directory": str(runtime_directory),
        "application_images": {
            "django": manifest["images"]["django"],
            "next": manifest["images"]["next"],
        },
        "edge_image": manifest["images"]["edge"],
    }


def verify_reference(reference):
    manifest_path = Path(reference["manifest_path"])
    manifest = load_manifest(manifest_path)
    if (
        manifest["release_sha"] != reference["release_sha"]
        or sha256(manifest_path) != reference["manifest_sha256"]
        or {
            "django": manifest["images"]["django"],
            "next": manifest["images"]["next"],
        }
        != reference["application_images"]
        or manifest["images"]["edge"] != reference["edge_image"]
    ):
        raise ValueError("immutable release manifest changed after attempt creation")


def snapshot_for_deploy(environment, reference, active, sequence, operation_id):
    return {
        "application": reference,
        "edge": reference
        if environment == "production"
        else (active["edge"] if active else None),
        "deployment_sequence": sequence,
        "activated_by_operation_id": operation_id,
    }


def operation_plan(attempt):
    if attempt["kind"] == "deploy":
        database_phase = (
            [
                "bootstrap-volume-authorized",
                "bootstrap-database-ready",
                "initial-backup-completed",
            ]
            if attempt["first_deploy"]
            else ["pre-migration-backup-completed"]
        )
        phases = [
            "attempt-recorded",
            *database_phase,
            "migration-started",
            "migration-completed",
            "application-healthy",
        ]
    else:
        phases = [
            "attempt-recorded",
            "recovery-backup-completed",
            "application-healthy",
        ]
    phases.extend(
        [
            (
                "edge-healthy"
                if attempt["environment"] == "production"
                else "edge-candidate-verified"
            ),
            "pending-public-smoke",
            "complete",
        ]
    )
    return phases


def validate_operation_id(operation_id):
    if not OPERATION_ID.fullmatch(operation_id):
        raise ValueError("operation ID must be 8-128 safe immutable characters")


def begin(args):
    validate_operation_id(args.operation_id)
    state = load_state(args.state_directory, args.environment)
    reference = release_reference(args.manifest, args.runtime_directory)
    if reference["release_sha"] != args.release_sha:
        raise ValueError("operation release SHA does not match immutable manifest")
    sequence = int(args.deployment_sequence)
    if sequence < 1:
        raise ValueError("deployment sequence must be positive")
    existing = state["attempts"].get(args.operation_id)
    if existing:
        if (
            existing["kind"] != args.operation
            or existing["deployment_sequence"] != sequence
            or existing["candidate"]["application"] != reference
        ):
            raise ValueError(
                "operation ID is already bound to conflicting immutable input"
            )
        if existing["status"] == "failed":
            raise ValueError("failed operation requires a separate reviewed recovery")
        return state

    if args.operation == "deploy":
        if state["recovery_required_for"]:
            raise ValueError(
                "failed rollout requires reviewed recovery before deployment"
            )
        if state["active"] and (
            sequence < state["active"]["deployment_sequence"]
            or (
                sequence == state["active"]["deployment_sequence"]
                and reference["release_sha"]
                != state["active"]["application"]["release_sha"]
            )
        ):
            raise ValueError(
                "deployment operation is stale or conflicts with active state"
            )
        if (
            state["active"]
            and reference["release_sha"]
            == state["active"]["application"]["release_sha"]
            and args.operation_id not in state["attempts"]
        ):
            raise ValueError("a different operation already activated this release")
        candidate = snapshot_for_deploy(
            args.environment,
            reference,
            state["active"],
            sequence,
            args.operation_id,
        )
    elif args.operation == "rollback":
        if state["recovery_required_for"]:
            raise ValueError("failed rollout requires recovery, not normal rollback")
        if not state["active"] or not state["previous"]:
            raise ValueError("rollback requires active and previous state")
        if sequence <= state["active"]["deployment_sequence"]:
            raise ValueError("rollback deployment sequence must advance active state")
        if (
            reference["release_sha"] != state["previous"]["application"]["release_sha"]
            or reference["manifest_sha256"]
            != state["previous"]["application"]["manifest_sha256"]
        ):
            raise ValueError(
                "rollback target is not the authoritative previous release"
            )
        candidate = {
            **state["previous"],
            "deployment_sequence": sequence,
            "activated_by_operation_id": args.operation_id,
        }
    else:
        raise ValueError("begin supports deploy or rollback operations")

    expected = {
        "operation_id": args.operation_id,
        "kind": args.operation,
        "environment": args.environment,
        "status": "in-progress",
        "phase": "attempt-recorded",
        "phase_history": ["attempt-recorded"],
        "deployment_sequence": sequence,
        "candidate": candidate,
        "base_active": state["active"],
        "base_previous": state["previous"],
        "first_deploy": state["active"] is None,
        "recovers_operation_id": None,
        "created_at": now(),
        "updated_at": now(),
        "evidence": [],
    }
    if state["in_progress_operation_id"]:
        raise ValueError("another rollout operation is already in progress")
    state["attempts"][args.operation_id] = expected
    state["in_progress_operation_id"] = args.operation_id
    save_state(args, state, "begin")
    return state


def begin_recovery(args):
    validate_operation_id(args.operation_id)
    validate_operation_id(args.failed_operation_id)
    state = load_state(args.state_directory, args.environment)
    sequence = int(args.deployment_sequence)
    existing = state["attempts"].get(args.operation_id)
    if existing:
        if (
            existing["kind"] != "recovery"
            or existing["deployment_sequence"] != sequence
            or existing["recovers_operation_id"] != args.failed_operation_id
        ):
            raise ValueError("recovery operation ID has conflicting immutable input")
        return state
    failed = state["attempts"].get(args.failed_operation_id)
    if (
        state["recovery_required_for"] != args.failed_operation_id
        or not failed
        or failed["status"] != "failed"
    ):
        raise ValueError("recovery target is not the authoritative failed operation")
    if not failed["base_active"]:
        raise ValueError("failed first deployment has no active release to recover")
    if sequence <= failed["deployment_sequence"]:
        raise ValueError("recovery deployment sequence must advance failed operation")
    candidate = {
        **failed["base_active"],
        "deployment_sequence": sequence,
        "activated_by_operation_id": args.operation_id,
    }
    expected = {
        "operation_id": args.operation_id,
        "kind": "recovery",
        "environment": args.environment,
        "status": "in-progress",
        "phase": "attempt-recorded",
        "phase_history": ["attempt-recorded"],
        "deployment_sequence": sequence,
        "candidate": candidate,
        "base_active": state["active"],
        "base_previous": state["previous"],
        "first_deploy": False,
        "recovers_operation_id": args.failed_operation_id,
        "created_at": now(),
        "updated_at": now(),
        "evidence": [],
    }
    if state["in_progress_operation_id"]:
        raise ValueError("another rollout operation is already in progress")
    state["attempts"][args.operation_id] = expected
    state["in_progress_operation_id"] = args.operation_id
    save_state(args, state, "begin-recovery")
    return state


def get_attempt(state, operation_id):
    attempt = state["attempts"].get(operation_id)
    if not attempt:
        raise ValueError("unknown rollout operation ID")
    return attempt


def checkpoint(args):
    state = load_state(args.state_directory, args.environment)
    attempt = get_attempt(state, args.operation_id)
    plan = operation_plan(attempt)
    if args.phase not in plan:
        raise ValueError("checkpoint is not valid for this operation")
    if args.phase in attempt["phase_history"]:
        return state
    if attempt["status"] != "in-progress":
        raise ValueError("only an in-progress operation can advance")
    if state["in_progress_operation_id"] != args.operation_id:
        raise ValueError("operation does not own the authoritative mutation lease")
    current_index = plan.index(attempt["phase"])
    if plan[current_index + 1] != args.phase:
        raise ValueError("checkpoint is stale or skips a required transition")
    attempt["phase"] = args.phase
    attempt["phase_history"].append(args.phase)
    attempt["updated_at"] = now()
    save_state(args, state, f"checkpoint-{args.phase}")
    return state


def needs_checkpoint(args):
    state = load_state(args.state_directory, args.environment)
    attempt = get_attempt(state, args.operation_id)
    plan = operation_plan(attempt)
    if args.phase not in plan:
        raise ValueError("checkpoint is not valid for this operation")
    return args.phase not in attempt["phase_history"]


def fail(args):
    state = load_state(args.state_directory, args.environment)
    attempt = get_attempt(state, args.operation_id)
    if attempt["status"] == "failed":
        return state
    if (
        attempt["status"] != "in-progress"
        or attempt["phase"] != "pending-public-smoke"
        or state["in_progress_operation_id"] != args.operation_id
    ):
        raise ValueError("only the pending public-smoke operation may be failed")
    attempt["status"] = "failed"
    attempt["phase"] = "failed-public-smoke"
    attempt["phase_history"].append("failed-public-smoke")
    attempt["updated_at"] = now()
    attempt["evidence"].append(
        {
            "kind": "public-smoke-failure",
            "recorded_at": now(),
            "detail": args.reason,
        }
    )
    state["in_progress_operation_id"] = None
    state["recovery_required_for"] = args.operation_id
    save_state(args, state, "fail-public-smoke")
    return state


def finalize(args):
    state = load_state(args.state_directory, args.environment)
    attempt = get_attempt(state, args.operation_id)
    if attempt["status"] == "completed":
        return state
    if (
        attempt["status"] != "in-progress"
        or attempt["phase"] != "pending-public-smoke"
        or state["in_progress_operation_id"] != args.operation_id
    ):
        raise ValueError("operation is not pending successful public smoke")
    verify_reference(attempt["candidate"]["application"])
    if args.environment == "production":
        verify_reference(attempt["candidate"]["edge"])
    if attempt["kind"] == "recovery":
        if state["recovery_required_for"] != attempt["recovers_operation_id"]:
            raise ValueError(
                "recovery no longer targets authoritative failure evidence"
            )
        state["active"] = attempt["candidate"]
        state["recovery_required_for"] = None
    else:
        state["previous"] = state["active"]
        state["active"] = attempt["candidate"]
    attempt["status"] = "completed"
    attempt["phase"] = "complete"
    attempt["phase_history"].append("complete")
    attempt["updated_at"] = now()
    attempt["evidence"].append({"kind": "public-smoke-success", "recorded_at": now()})
    state["in_progress_operation_id"] = None
    save_state(args, state, "finalize")
    return state


def abort(args):
    state = load_state(args.state_directory, args.environment)
    attempt = get_attempt(state, args.operation_id)
    if attempt["status"] == "aborted":
        return state
    if (
        attempt["status"] != "in-progress"
        or attempt["phase"] != "attempt-recorded"
        or state["in_progress_operation_id"] != args.operation_id
    ):
        raise ValueError("abort is allowed only before the first runtime mutation")
    attempt["status"] = "aborted"
    attempt["phase"] = "aborted"
    attempt["phase_history"].append("aborted")
    attempt["updated_at"] = now()
    attempt["evidence"].append(
        {"kind": "reviewed-abort", "recorded_at": now(), "detail": args.reason}
    )
    state["in_progress_operation_id"] = None
    save_state(args, state, "abort")
    return state


def field_value(value, field):
    for part in field.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"state field does not exist: {field}")
        value = value[part]
    return value


def inspect(args):
    state = load_state(args.state_directory, args.environment)
    value = get_attempt(state, args.operation_id) if args.operation_id else state
    if args.field:
        value = field_value(value, args.field)
    if isinstance(value, (dict, list)) or value is None:
        print(json.dumps(value, sort_keys=True))
    elif isinstance(value, bool):
        print("true" if value else "false")
    else:
        print(value)


def parser():
    result = argparse.ArgumentParser()
    result.add_argument(
        "action",
        choices=(
            "begin",
            "begin-recovery",
            "checkpoint",
            "needs",
            "fail",
            "finalize",
            "abort",
            "inspect",
        ),
    )
    result.add_argument(
        "--environment", choices=("staging", "production"), required=True
    )
    result.add_argument(
        "--state-directory",
        type=Path,
        default=Path(os.environ.get("STATE_DIRECTORY", "/srv/kirillwynn/state")),
    )
    result.add_argument("--operation-id")
    result.add_argument("--failed-operation-id")
    result.add_argument("--operation", choices=("deploy", "rollback"))
    result.add_argument("--release-sha")
    result.add_argument("--manifest", type=Path)
    result.add_argument("--runtime-directory", type=Path)
    result.add_argument("--deployment-sequence")
    result.add_argument("--phase")
    result.add_argument("--reason", default="reviewed operator request")
    result.add_argument("--field")
    return result


def main():
    args = parser().parse_args()
    try:
        if args.action == "begin":
            required = (
                args.operation_id,
                args.operation,
                args.release_sha,
                args.manifest,
                args.runtime_directory,
                args.deployment_sequence,
            )
            if not all(value is not None for value in required):
                raise ValueError("begin requires complete immutable operation input")
            begin(args)
        elif args.action == "begin-recovery":
            required = (
                args.operation_id,
                args.failed_operation_id,
                args.deployment_sequence,
            )
            if not all(value is not None for value in required):
                raise ValueError("begin-recovery requires operation IDs and sequence")
            begin_recovery(args)
        elif args.action == "checkpoint":
            if not args.operation_id or not args.phase:
                raise ValueError("checkpoint requires operation ID and phase")
            checkpoint(args)
        elif args.action == "needs":
            if not args.operation_id or not args.phase:
                raise ValueError("needs requires operation ID and phase")
            raise SystemExit(0 if needs_checkpoint(args) else 1)
        elif args.action == "fail":
            if not args.operation_id:
                raise ValueError("fail requires operation ID")
            fail(args)
        elif args.action == "finalize":
            if not args.operation_id:
                raise ValueError("finalize requires operation ID")
            finalize(args)
        elif args.action == "abort":
            if not args.operation_id:
                raise ValueError("abort requires operation ID")
            abort(args)
        else:
            inspect(args)
    except (OSError, RuntimeError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
