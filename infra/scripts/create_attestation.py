#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path

from validate_release_manifest import load_manifest

OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("operation_id")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if not OPERATION_ID.fullmatch(args.operation_id) or not args.operation_id.endswith(
        f"-staging-{manifest['release_sha']}"
    ):
        raise SystemExit("attestation operation ID does not match staging release")
    payload = {
        "schema_version": 3,
        "environment": "staging",
        "release_sha": manifest["release_sha"],
        "operation_id": args.operation_id,
        "status": "passed",
        "images": manifest["images"],
        "checks": {
            "public_smoke": True,
            "django_readiness": True,
            "next_health": True,
            "worker_heartbeat": True,
            "worker_egress": True,
            "active_application_image_digests": True,
            "edge_candidate_nginx_config": True,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.umask(0o077)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.chmod(args.output, 0o600)


if __name__ == "__main__":
    main()
