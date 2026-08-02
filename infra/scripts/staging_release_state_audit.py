#!/usr/bin/env python3
"""Validate and summarize the authoritative staging rollout state without secrets."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import record_rollout_state


def bounded_reference(reference):
    record_rollout_state.verify_reference(reference)
    return {
        "release_sha": reference["release_sha"],
        "manifest_path": reference["manifest_path"],
        "manifest_sha256": reference["manifest_sha256"],
        "runtime_directory": reference["runtime_directory"],
        "application_images": reference["application_images"],
        "edge_image": reference["edge_image"],
    }


def bounded_snapshot(snapshot):
    if snapshot is None:
        return None
    return {
        "application": bounded_reference(snapshot["application"]),
        "edge": bounded_reference(snapshot["edge"]) if snapshot["edge"] else None,
        "deployment_sequence": snapshot["deployment_sequence"],
        "activated_by_operation_id": snapshot["activated_by_operation_id"],
    }


def require_release_layout(reference, release_directory, runtime_directory):
    release_sha = reference["release_sha"]
    expected_release = release_directory / release_sha
    expected_runtime = runtime_directory / release_sha / "staging"
    manifest_path = Path(reference["manifest_path"]).resolve(strict=True)
    runtime_directory = Path(reference["runtime_directory"]).resolve(strict=True)
    if manifest_path != expected_release / "release-manifest.json":
        raise ValueError("active staging manifest is outside the immutable release layout")
    if runtime_directory != expected_runtime:
        raise ValueError("active staging runtime is outside the release-scoped layout")


def build_report(
    state,
    expected_release_sha,
    release_directory=Path("/srv/kirillwynn/releases"),
    runtime_directory=Path("/srv/kirillwynn/runtime/releases"),
):
    active = state["active"]
    if active is None:
        raise ValueError("staging has no active application snapshot")
    if active["application"]["release_sha"] != expected_release_sha:
        raise ValueError("active staging application release differs from the audit input")
    if active["edge"] is None:
        raise ValueError("staging has no authoritative shared Edge snapshot")
    if state["in_progress_operation_id"] is not None:
        raise ValueError("staging has an in-progress rollout operation")
    if state["recovery_required_for"] is not None:
        raise ValueError("staging requires reviewed rollout recovery")

    require_release_layout(active["application"], release_directory, runtime_directory)
    require_release_layout(active["edge"], release_directory, runtime_directory)
    if state["previous"] is not None:
        require_release_layout(
            state["previous"]["application"], release_directory, runtime_directory
        )
        if state["previous"]["edge"] is not None:
            require_release_layout(state["previous"]["edge"], release_directory, runtime_directory)

    attempts = Counter(attempt["status"] for attempt in state["attempts"].values())
    database = state["database"]
    return {
        "schema": "stage18-staging-release-state-audit/v1",
        "rollout_schema_version": state["schema_version"],
        "rollout_revision": state["revision"],
        "active": bounded_snapshot(active),
        "previous": bounded_snapshot(state["previous"]),
        "database": {
            "lifecycle_state": database["lifecycle_state"],
            "volume_name": database["volume_name"],
            "postgres_image": database["postgres_image"],
            "bootstrap_operation_id": database["bootstrap_operation_id"],
            "last_backup": database["last_backup"],
            "last_migration": database["last_migration"],
        },
        "attempt_statuses": dict(sorted(attempts.items())),
        "in_progress_operation_id": None,
        "recovery_required_for": None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-active-release", required=True)
    parser.add_argument(
        "--state-directory",
        type=Path,
        default=Path("/srv/kirillwynn/state"),
    )
    parser.add_argument(
        "--release-directory",
        type=Path,
        default=Path("/srv/kirillwynn/releases"),
    )
    parser.add_argument(
        "--runtime-directory",
        type=Path,
        default=Path("/srv/kirillwynn/runtime/releases"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if record_rollout_state.SHA.fullmatch(args.expected_active_release) is None:
        print("expected active release must be a 40-character SHA", file=sys.stderr)
        raise SystemExit(2)
    try:
        state = record_rollout_state.load_state(args.state_directory, "staging")
        result = build_report(
            state,
            args.expected_active_release,
            args.release_directory,
            args.runtime_directory,
        )
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(rendered)
        else:
            print(rendered, end="")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"invalid staging rollout state: {error}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
