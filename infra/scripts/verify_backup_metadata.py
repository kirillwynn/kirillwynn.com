#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
CHECKSUM = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP = re.compile(r"^\d{8}T\d{6}Z$")
FIELDS = {
    "schema_version",
    "environment",
    "release_sha",
    "created_at",
    "sha256",
    "dump_file",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(dump, metadata, environment):
    payload = json.loads(metadata.read_text())
    if set(payload) != FIELDS or payload["schema_version"] != 1:
        raise ValueError("backup metadata shape or schema is invalid")
    if payload["environment"] != environment:
        raise ValueError("backup metadata environment does not match")
    if payload["dump_file"] != dump.name:
        raise ValueError("backup metadata dump_file does not match")
    if not SHA.fullmatch(payload["release_sha"]):
        raise ValueError("backup metadata release SHA is invalid")
    if not TIMESTAMP.fullmatch(payload["created_at"]):
        raise ValueError("backup metadata timestamp is invalid")
    if not CHECKSUM.fullmatch(payload["sha256"]):
        raise ValueError("backup metadata checksum is invalid")
    if sha256(dump) != payload["sha256"]:
        raise ValueError("backup SHA-256 mismatch")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=("staging", "production"))
    parser.add_argument("dump", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--print-release-sha", action="store_true")
    args = parser.parse_args()
    metadata = args.metadata or Path(f"{args.dump}.json")
    try:
        if not args.dump.is_file():
            raise ValueError("backup dump is missing")
        if not metadata.is_file():
            raise ValueError("backup metadata is missing")
        payload = verify(args.dump, metadata, args.environment)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"invalid backup: {error}", file=sys.stderr)
        raise SystemExit(2) from None
    if args.print_release_sha:
        print(payload["release_sha"], end="")


if __name__ == "__main__":
    main()
