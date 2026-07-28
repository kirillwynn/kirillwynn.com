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

SCHEMA_VERSION = 3
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
    "activation_policy",
    "environment",
    "status",
    "phase",
    "phase_history",
    "deployment_sequence",
    "candidate",
    "base_active",
    "base_previous",
    "base_database",
    "database_identity",
    "database_start_state",
    "database_initial_backup_present",
    "first_deploy",
    "recovers_operation_id",
    "resolution_kind",
    "created_at",
    "updated_at",
    "evidence",
    "failure",
}
DATABASE_FIELDS = {
    "environment",
    "lifecycle_state",
    "volume_name",
    "postgres_image",
    "bootstrap_runtime_directory",
    "bootstrap_operation_id",
    "initial_backup",
    "last_backup",
    "last_migration",
}
DATABASE_IDENTITY_FIELDS = {
    "environment",
    "volume_name",
    "postgres_image",
    "bootstrap_runtime_directory",
    "bootstrap_operation_id",
}
BACKUP_FIELDS = {
    "operation_id",
    "purpose",
    "release_sha",
    "recorded_at",
}
MIGRATION_FIELDS = {
    "operation_id",
    "release_sha",
    "manifest_sha256",
    "runtime_directory",
    "recorded_at",
}
FAILURE_FIELDS = {
    "failed_at_phase",
    "category",
    "reason",
    "recorded_at",
    "candidate",
    "base_active",
    "base_previous",
    "base_database",
    "database_at_failure",
    "possible_side_effects",
    "resolution",
}
RESOLUTION_FIELDS = {
    "status",
    "kind",
    "operation_id",
    "claimed_at",
    "completed_at",
}
FAILURE_CATEGORIES = {
    "runtime-mutation",
    "remote-rollout",
    "public-smoke",
    "pre-finalize-attestation",
    "operator",
}
ACTIVATION_POLICIES = {
    "preserve-previous",
    "rotate-active-to-previous",
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
        "database": {
            "environment": environment,
            "lifecycle_state": "absent",
            "volume_name": None,
            "postgres_image": None,
            "bootstrap_runtime_directory": None,
            "bootstrap_operation_id": None,
            "initial_backup": None,
            "last_backup": None,
            "last_migration": None,
        },
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


def validate_database_identity(identity, environment):
    if (
        not isinstance(identity, dict)
        or set(identity) != DATABASE_IDENTITY_FIELDS
        or identity["environment"] != environment
        or not isinstance(identity["volume_name"], str)
        or not identity["volume_name"]
        or not isinstance(identity["postgres_image"], str)
        or "@sha256:" not in identity["postgres_image"]
        or not isinstance(identity["bootstrap_runtime_directory"], str)
        or not Path(identity["bootstrap_runtime_directory"]).is_absolute()
        or not OPERATION_ID.fullmatch(identity["bootstrap_operation_id"])
    ):
        raise ValueError("authoritative database ownership identity is invalid")


def validate_backup_shape(backup):
    if (
        not isinstance(backup, dict)
        or set(backup) != BACKUP_FIELDS
        or not OPERATION_ID.fullmatch(backup.get("operation_id", ""))
        or backup.get("purpose")
        not in {"initial-empty", "pre-migration", "recovery", "manual"}
        or not SHA.fullmatch(backup.get("release_sha", ""))
        or not isinstance(backup.get("recorded_at"), str)
    ):
        raise ValueError("authoritative database backup evidence is invalid")


def validate_database_shape(database, environment):
    if (
        not isinstance(database, dict)
        or set(database) != DATABASE_FIELDS
        or database["environment"] != environment
        or database["lifecycle_state"]
        not in {"absent", "authorized", "ready", "migrated"}
    ):
        raise ValueError("authoritative database lifecycle snapshot is invalid")
    if database["lifecycle_state"] == "absent":
        if any(
            database[field] is not None
            for field in DATABASE_FIELDS - {"environment", "lifecycle_state"}
        ):
            raise ValueError("absent database cannot contain ownership evidence")
        return
    validate_database_identity(
        {field: database[field] for field in DATABASE_IDENTITY_FIELDS},
        environment,
    )
    if database["initial_backup"] is not None:
        validate_backup_shape(database["initial_backup"])
        if database["initial_backup"]["purpose"] != "initial-empty":
            raise ValueError("initial database backup has the wrong purpose")
    if database["last_backup"] is not None:
        validate_backup_shape(database["last_backup"])
    migration = database["last_migration"]
    if migration is not None:
        if (
            not isinstance(migration, dict)
            or set(migration) != MIGRATION_FIELDS
            or not OPERATION_ID.fullmatch(migration.get("operation_id", ""))
            or not SHA.fullmatch(migration.get("release_sha", ""))
            or not CHECKSUM.fullmatch(migration.get("manifest_sha256", ""))
            or not isinstance(migration.get("runtime_directory"), str)
            or not Path(migration["runtime_directory"]).is_absolute()
            or not isinstance(migration.get("recorded_at"), str)
        ):
            raise ValueError("authoritative migration boundary is invalid")
    if database["lifecycle_state"] == "authorized" and (
        database["initial_backup"] is not None or migration is not None
    ):
        raise ValueError("authorized database contains post-bootstrap evidence")
    if database["lifecycle_state"] == "migrated" and migration is None:
        raise ValueError("migrated database lacks a migration boundary")


def validate_resolution_shape(resolution):
    if resolution is None:
        return
    if (
        not isinstance(resolution, dict)
        or set(resolution) != RESOLUTION_FIELDS
        or resolution["status"] not in {"in-progress", "completed", "failed"}
        or resolution["kind"] not in {"recovery", "retry", "fix-forward"}
        or not OPERATION_ID.fullmatch(resolution.get("operation_id", ""))
        or not isinstance(resolution.get("claimed_at"), str)
        or (
            resolution["status"] == "completed"
            and not isinstance(resolution.get("completed_at"), str)
        )
        or (
            resolution["status"] != "completed"
            and resolution.get("completed_at") is not None
        )
    ):
        raise ValueError("authoritative failure resolution ownership is invalid")


def validate_failure_shape(failure, attempt, environment):
    if failure is None:
        return
    if (
        not isinstance(failure, dict)
        or set(failure) != FAILURE_FIELDS
        or not isinstance(failure.get("failed_at_phase"), str)
        or failure.get("category") not in FAILURE_CATEGORIES
        or not isinstance(failure.get("reason"), str)
        or not failure["reason"]
        or len(failure["reason"]) > 512
        or any(ord(character) < 32 for character in failure["reason"])
        or not isinstance(failure.get("recorded_at"), str)
        or not isinstance(failure.get("possible_side_effects"), list)
        or not all(
            isinstance(item, str) and item for item in failure["possible_side_effects"]
        )
        or failure["candidate"] != attempt["candidate"]
        or failure["base_active"] != attempt["base_active"]
        or failure["base_previous"] != attempt["base_previous"]
        or failure["base_database"] != attempt["base_database"]
    ):
        raise ValueError("authoritative rollout failure evidence is invalid")
    validate_snapshot_shape(failure["candidate"], environment)
    for snapshot in (failure["base_active"], failure["base_previous"]):
        if snapshot is not None:
            validate_snapshot_shape(snapshot, environment)
    validate_database_shape(failure["base_database"], environment)
    validate_database_shape(failure["database_at_failure"], environment)
    validate_resolution_shape(failure["resolution"])


def validate_attempt_shape(operation_id, attempt, environment):
    if (
        not OPERATION_ID.fullmatch(operation_id)
        or not isinstance(attempt, dict)
        or set(attempt) != ATTEMPT_FIELDS
        or attempt["operation_id"] != operation_id
        or attempt["environment"] != environment
        or attempt["kind"]
        not in {"deploy", "rollback", "recovery", "retry", "fix-forward"}
        or attempt["activation_policy"] not in ACTIVATION_POLICIES
        or attempt["status"] not in {"in-progress", "completed", "failed", "aborted"}
        or not isinstance(attempt["deployment_sequence"], int)
        or attempt["deployment_sequence"] < 1
        or not isinstance(attempt["first_deploy"], bool)
        or attempt["database_start_state"]
        not in {"absent", "authorized", "ready", "migrated"}
        or not isinstance(attempt["database_initial_backup_present"], bool)
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
    validate_database_shape(attempt["base_database"], environment)
    validate_database_identity(attempt["database_identity"], environment)
    recovery_id = attempt["recovers_operation_id"]
    if attempt["kind"] in {"recovery", "retry", "fix-forward"}:
        if not isinstance(recovery_id, str) or not OPERATION_ID.fullmatch(recovery_id):
            raise ValueError("resolution attempt does not identify failed evidence")
        if attempt["resolution_kind"] != attempt["kind"]:
            raise ValueError("resolution attempt kind is inconsistent")
    elif recovery_id is not None:
        raise ValueError("non-recovery attempt contains a recovery target")
    elif attempt["resolution_kind"] is not None:
        raise ValueError("ordinary attempt contains resolution ownership")
    expected_terminal = {
        "completed": "complete",
        "failed": "failed",
        "aborted": "aborted",
    }
    if attempt["status"] in expected_terminal:
        if attempt["phase"] != expected_terminal[attempt["status"]]:
            raise ValueError("attempt status and terminal phase disagree")
    elif attempt["phase"] not in operation_plan(attempt)[:-1]:
        raise ValueError("in-progress attempt phase is invalid")
    if (attempt["status"] == "failed") != (attempt["failure"] is not None):
        raise ValueError("attempt status and failure evidence disagree")
    validate_failure_shape(attempt["failure"], attempt, environment)


def validate_state_shape(state, environment):
    if (
        set(state)
        != {
            "schema_version",
            "environment",
            "revision",
            "active",
            "previous",
            "database",
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
    validate_database_shape(state["database"], environment)
    for operation_id, attempt in state["attempts"].items():
        validate_attempt_shape(operation_id, attempt, environment)


def validate_activation_policy_lineage(state):
    attempts = state["attempts"]
    visiting = set()
    validated = {}

    def inherited_policy(operation_id):
        if operation_id in validated:
            return validated[operation_id]
        if operation_id in visiting:
            raise ValueError("authoritative activation policy lineage contains a cycle")
        visiting.add(operation_id)
        attempt = attempts[operation_id]
        kind = attempt["kind"]
        if kind == "retry":
            failed_operation_id = attempt["recovers_operation_id"]
            failed = attempts.get(failed_operation_id)
            if failed is None:
                raise ValueError(
                    "authoritative activation policy lineage has no failed operation"
                )
            expected = inherited_policy(failed_operation_id)
            if (
                attempt["candidate"]["application"]
                != failed["candidate"]["application"]
            ):
                raise ValueError(
                    "authoritative retry activation lineage changed exact candidate"
                )
        elif kind == "recovery":
            expected = "preserve-previous"
        else:
            expected = "rotate-active-to-previous"
        visiting.remove(operation_id)
        if attempt["activation_policy"] != expected:
            raise ValueError(
                "authoritative activation policy conflicts with operation lineage"
            )
        validated[operation_id] = expected
        return expected

    for operation_id in attempts:
        inherited_policy(operation_id)


def same_component_snapshot(first, second):
    return (
        first is not None
        and second is not None
        and first["application"] == second["application"]
        and first["edge"] == second["edge"]
    )


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
    validate_activation_policy_lineage(state)
    if same_component_snapshot(state["active"], state["previous"]):
        raise ValueError(
            "authoritative active and previous component snapshots are identical"
        )
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
    for failed_operation_id, failed in state["attempts"].items():
        failure = failed["failure"]
        if failure is None or failure["resolution"] is None:
            continue
        resolution = failure["resolution"]
        owner = state["attempts"].get(resolution["operation_id"])
        if (
            owner is None
            or owner["kind"] != resolution["kind"]
            or owner["recovers_operation_id"] != failed_operation_id
            or owner["status"] != resolution["status"]
        ):
            raise ValueError(
                "authoritative rollout state has invalid resolution ownership"
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
    kind = attempt["kind"]
    database_state = attempt["database_start_state"]
    initial_backup_present = attempt["database_initial_backup_present"]
    if kind in {"deploy", "retry", "fix-forward"}:
        if database_state == "absent":
            database_phases = [
                "bootstrap-volume-authorized",
                "bootstrap-database-ready",
                "initial-backup-started",
                "initial-backup-completed",
            ]
        elif kind in {"retry", "fix-forward"} and database_state == "authorized":
            database_phases = [
                "bootstrap-database-ready",
            ]
            if kind == "retry":
                database_phases.extend(
                    ["initial-backup-started", "initial-backup-completed"]
                )
            else:
                database_phases.extend(
                    ["recovery-backup-started", "recovery-backup-completed"]
                )
        elif (
            kind == "retry" and database_state == "ready" and not initial_backup_present
        ):
            database_phases = [
                "initial-backup-started",
                "initial-backup-completed",
            ]
        else:
            backup_prefix = "pre-migration" if kind == "deploy" else "recovery"
            database_phases = [
                f"{backup_prefix}-backup-started",
                f"{backup_prefix}-backup-completed",
            ]
        phases = [
            "attempt-recorded",
            *database_phases,
            "migration-started",
            "migration-completed",
            "application-rollout-started",
            "application-healthy",
        ]
    else:
        phases = [
            "attempt-recorded",
            "recovery-backup-started",
            "recovery-backup-completed",
            "application-rollout-started",
            "application-healthy",
        ]
    phases.extend(
        [
            "edge-rollout-started",
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


def database_identity(args, state, operation_id):
    if state["database"]["lifecycle_state"] == "absent":
        bootstrap_operation_id = operation_id
        bootstrap_runtime_directory = str(args.runtime_directory.resolve())
    else:
        bootstrap_operation_id = state["database"]["bootstrap_operation_id"]
        bootstrap_runtime_directory = state["database"]["bootstrap_runtime_directory"]
    identity = {
        "environment": args.environment,
        "volume_name": args.postgres_volume,
        "postgres_image": args.postgres_image,
        "bootstrap_runtime_directory": bootstrap_runtime_directory,
        "bootstrap_operation_id": bootstrap_operation_id,
    }
    validate_database_identity(identity, args.environment)
    if state["database"]["lifecycle_state"] != "absent":
        durable = {
            field: state["database"][field] for field in DATABASE_IDENTITY_FIELDS
        }
        if identity != durable:
            raise ValueError("incoming database identity conflicts with owned database")
    return identity


def begin(args):
    validate_operation_id(args.operation_id)
    state = load_state(args.state_directory, args.environment)
    reference = release_reference(args.manifest, args.runtime_directory)
    if reference["release_sha"] != args.release_sha:
        raise ValueError("operation release SHA does not match immutable manifest")
    sequence = int(args.deployment_sequence)
    if sequence < 1:
        raise ValueError("deployment sequence must be positive")
    identity = database_identity(args, state, args.operation_id)
    existing = state["attempts"].get(args.operation_id)
    if existing:
        if (
            existing["kind"] != args.operation
            or existing["deployment_sequence"] != sequence
            or existing["candidate"]["application"] != reference
            or existing["database_identity"] != identity
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
        "activation_policy": "rotate-active-to-previous",
        "environment": args.environment,
        "status": "in-progress",
        "phase": "attempt-recorded",
        "phase_history": ["attempt-recorded"],
        "deployment_sequence": sequence,
        "candidate": candidate,
        "base_active": state["active"],
        "base_previous": state["previous"],
        "base_database": state["database"],
        "database_identity": identity,
        "database_start_state": state["database"]["lifecycle_state"],
        "database_initial_backup_present": (
            state["database"]["initial_backup"] is not None
        ),
        "first_deploy": state["active"] is None,
        "recovers_operation_id": None,
        "resolution_kind": None,
        "created_at": now(),
        "updated_at": now(),
        "evidence": [],
        "failure": None,
    }
    if state["in_progress_operation_id"]:
        raise ValueError("another rollout operation is already in progress")
    state["attempts"][args.operation_id] = expected
    state["in_progress_operation_id"] = args.operation_id
    save_state(args, state, "begin")
    return state


def claim_failure_resolution(failed, operation_id, kind):
    resolution = failed["failure"]["resolution"]
    expected = {
        "status": "in-progress",
        "kind": kind,
        "operation_id": operation_id,
        "claimed_at": None,
        "completed_at": None,
    }
    if resolution is not None:
        if resolution["operation_id"] != operation_id or resolution["kind"] != kind:
            raise ValueError("failed operation is owned by another resolution")
        return
    expected["claimed_at"] = now()
    failed["failure"]["resolution"] = expected


def resolution_target(state, args):
    failed = state["attempts"].get(args.failed_operation_id)
    if (
        state["recovery_required_for"] != args.failed_operation_id
        or not failed
        or failed["status"] != "failed"
    ):
        raise ValueError("resolution target is not the authoritative failed operation")
    return failed


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
    failed = resolution_target(state, args)
    if not failed["base_active"]:
        raise ValueError("failed first deployment has no active release to recover")
    if sequence <= failed["deployment_sequence"]:
        raise ValueError("recovery deployment sequence must advance failed operation")
    candidate = {
        **failed["base_active"],
        "deployment_sequence": sequence,
        "activated_by_operation_id": args.operation_id,
    }
    durable_identity = {
        field: state["database"][field] for field in DATABASE_IDENTITY_FIELDS
    }
    validate_database_identity(durable_identity, args.environment)
    expected = {
        "operation_id": args.operation_id,
        "kind": "recovery",
        "activation_policy": "preserve-previous",
        "environment": args.environment,
        "status": "in-progress",
        "phase": "attempt-recorded",
        "phase_history": ["attempt-recorded"],
        "deployment_sequence": sequence,
        "candidate": candidate,
        "base_active": state["active"],
        "base_previous": state["previous"],
        "base_database": state["database"],
        "database_identity": durable_identity,
        "database_start_state": state["database"]["lifecycle_state"],
        "database_initial_backup_present": (
            state["database"]["initial_backup"] is not None
        ),
        "first_deploy": False,
        "recovers_operation_id": args.failed_operation_id,
        "resolution_kind": "recovery",
        "created_at": now(),
        "updated_at": now(),
        "evidence": [],
        "failure": None,
    }
    if state["in_progress_operation_id"]:
        raise ValueError("another rollout operation is already in progress")
    claim_failure_resolution(failed, args.operation_id, "recovery")
    state["attempts"][args.operation_id] = expected
    state["in_progress_operation_id"] = args.operation_id
    save_state(args, state, "begin-recovery")
    return state


def begin_resolution(args):
    validate_operation_id(args.operation_id)
    validate_operation_id(args.failed_operation_id)
    if args.resolution not in {"retry", "fix-forward"}:
        raise ValueError("deploy resolution must be retry or fix-forward")
    state = load_state(args.state_directory, args.environment)
    sequence = int(args.deployment_sequence)
    reference = release_reference(args.manifest, args.runtime_directory)
    if reference["release_sha"] != args.release_sha:
        raise ValueError("resolution release SHA does not match immutable manifest")
    identity = database_identity(args, state, args.operation_id)
    existing = state["attempts"].get(args.operation_id)
    if existing:
        if (
            existing["kind"] != args.resolution
            or existing["deployment_sequence"] != sequence
            or existing["recovers_operation_id"] != args.failed_operation_id
            or existing["candidate"]["application"] != reference
            or existing["database_identity"] != identity
        ):
            raise ValueError("resolution operation ID has conflicting immutable input")
        return state
    failed = resolution_target(state, args)
    if sequence <= failed["deployment_sequence"]:
        raise ValueError("resolution deployment sequence must advance failed operation")
    failed_reference = failed["candidate"]["application"]
    if args.resolution == "retry" and reference != failed_reference:
        raise ValueError("retry must use the exact failed candidate")
    if args.resolution == "fix-forward" and (
        reference["release_sha"] == failed_reference["release_sha"]
        or reference["manifest_sha256"] == failed_reference["manifest_sha256"]
    ):
        raise ValueError("fix-forward requires a new immutable release")
    candidate = snapshot_for_deploy(
        args.environment,
        reference,
        state["active"],
        sequence,
        args.operation_id,
    )
    expected = {
        "operation_id": args.operation_id,
        "kind": args.resolution,
        "activation_policy": (
            failed["activation_policy"]
            if args.resolution == "retry"
            else "rotate-active-to-previous"
        ),
        "environment": args.environment,
        "status": "in-progress",
        "phase": "attempt-recorded",
        "phase_history": ["attempt-recorded"],
        "deployment_sequence": sequence,
        "candidate": candidate,
        "base_active": state["active"],
        "base_previous": state["previous"],
        "base_database": state["database"],
        "database_identity": identity,
        "database_start_state": state["database"]["lifecycle_state"],
        "database_initial_backup_present": (
            state["database"]["initial_backup"] is not None
        ),
        "first_deploy": state["active"] is None,
        "recovers_operation_id": args.failed_operation_id,
        "resolution_kind": args.resolution,
        "created_at": now(),
        "updated_at": now(),
        "evidence": [],
        "failure": None,
    }
    if state["in_progress_operation_id"]:
        raise ValueError("another rollout operation is already in progress")
    claim_failure_resolution(failed, args.operation_id, args.resolution)
    state["attempts"][args.operation_id] = expected
    state["in_progress_operation_id"] = args.operation_id
    save_state(args, state, f"begin-{args.resolution}")
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
    database = state["database"]
    if args.phase == "bootstrap-volume-authorized":
        if database["lifecycle_state"] != "absent":
            raise ValueError("database bootstrap authorization is no longer absent")
        identity = attempt["database_identity"]
        database.update(identity)
        database["lifecycle_state"] = "authorized"
    elif args.phase == "bootstrap-database-ready":
        if (
            database["lifecycle_state"] != "authorized"
            or database["bootstrap_operation_id"]
            != attempt["database_identity"]["bootstrap_operation_id"]
        ):
            raise ValueError("database-ready checkpoint lacks bootstrap ownership")
        database["lifecycle_state"] = "ready"
    elif args.phase.endswith("-backup-completed"):
        purpose = {
            "initial-backup-completed": "initial-empty",
            "pre-migration-backup-completed": "pre-migration",
            "recovery-backup-completed": "recovery",
        }[args.phase]
        backup = {
            "operation_id": args.operation_id,
            "purpose": purpose,
            "release_sha": attempt["candidate"]["application"]["release_sha"],
            "recorded_at": now(),
        }
        database["last_backup"] = backup
        if purpose == "initial-empty":
            if database["lifecycle_state"] != "ready":
                raise ValueError("initial backup requires a ready database")
            if database["initial_backup"] is not None:
                raise ValueError("initial database backup is already recorded")
            database["initial_backup"] = backup
    elif args.phase == "migration-completed":
        if database["lifecycle_state"] not in {"ready", "migrated"}:
            raise ValueError("migration boundary requires an owned ready database")
        reference = attempt["candidate"]["application"]
        database["lifecycle_state"] = "migrated"
        database["last_migration"] = {
            "operation_id": args.operation_id,
            "release_sha": reference["release_sha"],
            "manifest_sha256": reference["manifest_sha256"],
            "runtime_directory": reference["runtime_directory"],
            "recorded_at": now(),
        }
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


def print_operation_plan(args):
    state = load_state(args.state_directory, args.environment)
    attempt = get_attempt(state, args.operation_id)
    for phase in operation_plan(attempt):
        print(phase)


def print_checkpoint_status(args):
    print("needed" if needs_checkpoint(args) else "complete")


def possible_side_effects(attempt):
    phase = attempt["phase"]
    if phase == "attempt-recorded":
        return ["no-runtime-mutation-checkpointed"]
    effects = ["owned-database-volume-may-exist"]
    if phase == "bootstrap-volume-authorized":
        return effects + ["postgres-container-or-database-may-have-started"]
    effects.append("postgres-container-or-database-may-be-running")
    if "backup" in phase:
        effects.append("purpose-typed-backup-may-exist")
    if phase.startswith("migration-") or phase in {
        "application-rollout-started",
        "application-healthy",
        "edge-rollout-started",
        "edge-healthy",
        "edge-candidate-verified",
        "pending-public-smoke",
    }:
        effects.append("database-schema-may-have-changed")
    if phase in {
        "application-rollout-started",
        "application-healthy",
        "edge-rollout-started",
        "edge-healthy",
        "edge-candidate-verified",
        "pending-public-smoke",
    }:
        effects.append("application-containers-may-have-been-replaced")
    if (
        phase
        in {
            "edge-rollout-started",
            "edge-healthy",
            "pending-public-smoke",
        }
        and attempt["environment"] == "production"
    ):
        effects.append("production-edge-may-have-been-replaced")
    if phase == "pending-public-smoke":
        effects.append("candidate-may-have-served-public-traffic")
    return effects


def validate_failure_input(args):
    if args.category not in FAILURE_CATEGORIES:
        raise ValueError("failure category is not bounded")
    reason = args.reason.strip()
    if (
        not reason
        or len(reason) > 512
        or any(ord(character) < 32 for character in reason)
    ):
        raise ValueError("failure reason must be 1-512 printable characters")
    return reason


def fail(args):
    state = load_state(args.state_directory, args.environment)
    attempt = get_attempt(state, args.operation_id)
    reason = validate_failure_input(args)
    if attempt["status"] == "failed":
        failure = attempt["failure"]
        if failure["category"] == args.category and failure["reason"] == reason:
            return state
        raise ValueError("conflicting failure evidence already exists")
    if (
        attempt["status"] != "in-progress"
        or state["in_progress_operation_id"] != args.operation_id
    ):
        raise ValueError("only an in-progress operation may fail")
    failed_at_phase = attempt["phase"]
    recorded_at = now()
    attempt["status"] = "failed"
    attempt["phase"] = "failed"
    attempt["phase_history"].append("failed")
    attempt["updated_at"] = recorded_at
    attempt["failure"] = {
        "failed_at_phase": failed_at_phase,
        "category": args.category,
        "reason": reason,
        "recorded_at": recorded_at,
        "candidate": attempt["candidate"],
        "base_active": attempt["base_active"],
        "base_previous": attempt["base_previous"],
        "base_database": attempt["base_database"],
        "database_at_failure": state["database"],
        "possible_side_effects": possible_side_effects(
            {**attempt, "phase": failed_at_phase}
        ),
        "resolution": None,
    }
    attempt["evidence"].append(
        {
            "kind": "rollout-failure",
            "recorded_at": recorded_at,
            "category": args.category,
            "failed_at_phase": failed_at_phase,
        }
    )
    if attempt["recovers_operation_id"] is not None:
        prior = get_attempt(state, attempt["recovers_operation_id"])
        resolution = prior["failure"]["resolution"]
        if resolution and resolution["operation_id"] == args.operation_id:
            resolution["status"] = "failed"
    state["in_progress_operation_id"] = None
    state["recovery_required_for"] = args.operation_id
    save_state(args, state, "fail")
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
    if attempt["resolution_kind"] is not None:
        if state["recovery_required_for"] != attempt["recovers_operation_id"]:
            raise ValueError(
                "resolution no longer targets authoritative failure evidence"
            )
        failed = get_attempt(state, attempt["recovers_operation_id"])
        resolution = failed["failure"]["resolution"]
        if (
            resolution is None
            or resolution["operation_id"] != args.operation_id
            or resolution["kind"] != attempt["resolution_kind"]
        ):
            raise ValueError("failure resolution ownership changed")
        resolution["status"] = "completed"
        resolution["completed_at"] = now()
        state["recovery_required_for"] = None
    if attempt["activation_policy"] == "preserve-previous":
        state["active"] = attempt["candidate"]
    elif attempt["activation_policy"] == "rotate-active-to-previous":
        state["previous"] = state["active"]
        state["active"] = attempt["candidate"]
    else:
        raise ValueError("operation has an unsupported activation policy")
    if same_component_snapshot(state["active"], state["previous"]):
        raise ValueError("activation would make active and previous identical")
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
            "begin-resolution",
            "checkpoint",
            "needs",
            "plan",
            "checkpoint-status",
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
    result.add_argument("--resolution", choices=("retry", "fix-forward"))
    result.add_argument("--release-sha")
    result.add_argument("--manifest", type=Path)
    result.add_argument("--runtime-directory", type=Path)
    result.add_argument("--deployment-sequence")
    result.add_argument("--postgres-volume")
    result.add_argument("--postgres-image")
    result.add_argument("--phase")
    result.add_argument("--reason", default="reviewed operator request")
    result.add_argument("--category", choices=tuple(sorted(FAILURE_CATEGORIES)))
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
                args.postgres_volume,
                args.postgres_image,
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
        elif args.action == "begin-resolution":
            required = (
                args.operation_id,
                args.failed_operation_id,
                args.resolution,
                args.release_sha,
                args.manifest,
                args.runtime_directory,
                args.deployment_sequence,
                args.postgres_volume,
                args.postgres_image,
            )
            if not all(value is not None for value in required):
                raise ValueError(
                    "begin-resolution requires complete immutable resolution input"
                )
            begin_resolution(args)
        elif args.action == "checkpoint":
            if not args.operation_id or not args.phase:
                raise ValueError("checkpoint requires operation ID and phase")
            checkpoint(args)
        elif args.action == "needs":
            if not args.operation_id or not args.phase:
                raise ValueError("needs requires operation ID and phase")
            raise SystemExit(0 if needs_checkpoint(args) else 1)
        elif args.action == "plan":
            if not args.operation_id:
                raise ValueError("plan requires operation ID")
            print_operation_plan(args)
        elif args.action == "checkpoint-status":
            if not args.operation_id or not args.phase:
                raise ValueError("checkpoint-status requires operation ID and phase")
            print_checkpoint_status(args)
        elif args.action == "fail":
            if not args.operation_id or not args.category:
                raise ValueError("fail requires operation ID and category")
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
