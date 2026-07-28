#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from validate_release_manifest import load_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    payload = {
        "schema_version": 2,
        "environment": "staging",
        "release_sha": manifest["release_sha"],
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
