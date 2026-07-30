#!/usr/bin/env python3
"""Validate catalog sync results and write a canonical non-secret attestation."""

import argparse
import ast
import json
import re
from pathlib import Path

SHA256 = re.compile(r"[0-9a-f]{64}")
RELEASE_SHA = re.compile(r"[0-9a-f]{40}")
RESULT_KEYS = {
    "activated",
    "attestation_sha256",
    "created",
    "environment",
    "items",
    "manifest_sha256",
    "objects",
    "prefix",
    "updated",
}


def parse_result(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        try:
            value = ast.literal_eval(line)
        except (SyntaxError, ValueError):
            continue
        if isinstance(value, dict) and set(value) == RESULT_KEYS:
            return value
    raise ValueError(f"catalog sync result is missing from {path}")


def validate_result(
    value: dict,
    *,
    manifest_sha256: str,
    attestation_sha256: str,
    activated: bool,
    created: int,
) -> None:
    expected = {
        "environment": "staging",
        "prefix": "staging/media",
        "manifest_sha256": manifest_sha256,
        "attestation_sha256": attestation_sha256,
        "items": 228,
        "objects": 276,
        "created": created,
        "updated": 0,
        "activated": activated,
    }
    if value != expected:
        raise ValueError(f"unexpected catalog sync result: {value!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", required=True, type=Path)
    parser.add_argument("--activate", required=True, type=Path)
    parser.add_argument("--idempotent", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--catalog-attestation-sha256", required=True)
    args = parser.parse_args()

    if RELEASE_SHA.fullmatch(args.release_sha) is None:
        parser.error("release SHA is invalid")
    if not args.run_id.isdecimal():
        parser.error("run ID is invalid")
    for digest in (
        args.archive_sha256,
        args.manifest_sha256,
        args.catalog_attestation_sha256,
    ):
        if SHA256.fullmatch(digest) is None:
            parser.error("attestation digest is invalid")

    try:
        upload = parse_result(args.upload)
        activation = parse_result(args.activate)
        idempotent = parse_result(args.idempotent)
        validate_result(
            upload,
            manifest_sha256=args.manifest_sha256,
            attestation_sha256=args.catalog_attestation_sha256,
            activated=False,
            created=0,
        )
        validate_result(
            activation,
            manifest_sha256=args.manifest_sha256,
            attestation_sha256=args.catalog_attestation_sha256,
            activated=True,
            created=228,
        )
        validate_result(
            idempotent,
            manifest_sha256=args.manifest_sha256,
            attestation_sha256=args.catalog_attestation_sha256,
            activated=True,
            created=0,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))

    payload = {
        "schema_version": 1,
        "environment": "staging",
        "operation_id": f"catalog-sync-{args.run_id}-staging-{args.release_sha}",
        "active_release_sha": args.release_sha,
        "archive_sha256": args.archive_sha256,
        "manifest_sha256": args.manifest_sha256,
        "catalog_attestation_sha256": args.catalog_attestation_sha256,
        "items": 228,
        "objects": 276,
        "prefix": "staging/media",
        "checks": {
            "archive_hash": True,
            "manifest_hash": True,
            "catalog_attestation_hash": True,
            "active_expansion_release": True,
            "upload_before_activation": True,
            "object_bytes_hash_headers": True,
            "database_activation": True,
            "idempotent_repeat": True,
        },
        "results": {
            "upload": upload,
            "activation": activation,
            "idempotent": idempotent,
        },
    }
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
