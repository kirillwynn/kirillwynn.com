#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from validate_release_manifest import load_manifest


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def pending(args):
    manifest = load_manifest(args.manifest)
    if manifest["release_sha"] != args.release_sha:
        raise ValueError("pending state SHA does not match manifest")
    environment_dir = args.state_directory / args.environment
    existing = (
        list(environment_dir.glob("pending-*.json")) if environment_dir.exists() else []
    )
    if any(path.name != f"pending-{args.release_sha}.json" for path in existing):
        raise ValueError("another rollout is pending public verification")
    payload = {
        "schema_version": 1,
        "status": "pending-public-smoke",
        "environment": args.environment,
        "release_sha": args.release_sha,
        "operation": args.operation,
        "deployment_sequence": int(args.deployment_sequence),
        "runtime_directory": str(args.runtime_directory),
        "manifest_path": str(args.manifest.resolve()),
        "images": manifest["images"],
        "checks": {
            "migration_once": args.operation == "deploy",
            "migration_skipped_for_rollback": args.operation == "rollback",
            "compose_wait": True,
            "django_readiness": True,
            "next_health": True,
            "worker_heartbeat": True,
            "worker_egress": True,
            "active_image_digests": True,
        },
    }
    atomic_json(environment_dir / f"pending-{args.release_sha}.json", payload)


def finalize(args):
    environment_dir = args.state_directory / args.environment
    pending_path = environment_dir / f"pending-{args.release_sha}.json"
    payload = json.loads(pending_path.read_text())
    if (
        payload.get("status") != "pending-public-smoke"
        or payload.get("environment") != args.environment
        or payload.get("release_sha") != args.release_sha
    ):
        raise ValueError("pending rollout state does not match finalization request")
    manifest_path = Path(payload["manifest_path"])
    manifest = load_manifest(manifest_path)
    if manifest["release_sha"] != args.release_sha:
        raise ValueError("durable manifest no longer matches pending rollout")
    current_manifest = environment_dir / "current-manifest.json"
    previous_manifest = environment_dir / "previous-manifest.json"
    if current_manifest.exists():
        shutil.copyfile(current_manifest, previous_manifest)
        os.chmod(previous_manifest, 0o600)
    descriptor, temporary = tempfile.mkstemp(
        dir=environment_dir, prefix=".current-manifest."
    )
    os.close(descriptor)
    try:
        shutil.copyfile(manifest_path, temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, current_manifest)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    active = {
        **payload,
        "status": "active",
        "checks": {**payload["checks"], "public_smoke": True},
    }
    atomic_json(environment_dir / "active-release.json", active)
    pending_path.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pending", "finalize"))
    parser.add_argument(
        "--environment", choices=("staging", "production"), required=True
    )
    parser.add_argument("--release-sha", required=True)
    parser.add_argument(
        "--state-directory",
        type=Path,
        default=Path(os.environ.get("STATE_DIRECTORY", "/srv/kirillwynn/state")),
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--runtime-directory", type=Path)
    parser.add_argument("--deployment-sequence")
    parser.add_argument("--operation", choices=("deploy", "rollback"), default="deploy")
    args = parser.parse_args()
    try:
        if args.action == "pending":
            if (
                not args.manifest
                or not args.runtime_directory
                or args.deployment_sequence is None
            ):
                raise ValueError(
                    "pending state requires manifest, runtime, and sequence"
                )
            pending(args)
        else:
            finalize(args)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
