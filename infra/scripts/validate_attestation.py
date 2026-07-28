#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

from validate_release_manifest import load_manifest

CHECKS = {
    "public_smoke",
    "django_readiness",
    "next_health",
    "worker_heartbeat",
    "worker_egress",
    "active_application_image_digests",
    "edge_candidate_nginx_config",
}
OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("attestation", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        attestation = json.loads(args.attestation.read_text())
        manifest = load_manifest(args.manifest)
        if set(attestation) != {
            "schema_version",
            "environment",
            "release_sha",
            "operation_id",
            "status",
            "images",
            "checks",
        }:
            raise ValueError("attestation has unexpected fields")
        if (
            attestation["schema_version"] != 3
            or attestation["environment"] != "staging"
            or attestation["status"] != "passed"
            or not OPERATION_ID.fullmatch(attestation["operation_id"])
            or not attestation["operation_id"].endswith(
                f"-staging-{manifest['release_sha']}"
            )
            or attestation["release_sha"] != manifest["release_sha"]
            or attestation["images"] != manifest["images"]
            or set(attestation["checks"]) != CHECKS
            or not all(attestation["checks"].values())
        ):
            raise ValueError("attestation does not prove the complete staging gate")
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"invalid staging attestation: {error}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
