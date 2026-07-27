#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST_IMAGE = re.compile(r"^[a-z0-9./_-]+(?::[a-zA-Z0-9._-]+)?@sha256:[0-9a-f]{64}$")
IMAGE_NAMES = {"django", "next", "edge"}


def load_manifest(path: Path):
    data = json.loads(path.read_text())
    if set(data) != {
        "schema_version",
        "release_sha",
        "repository",
        "built_at",
        "images",
    }:
        raise ValueError("release manifest has unexpected top-level fields")
    if data["schema_version"] != 1 or not SHA.fullmatch(data["release_sha"]):
        raise ValueError("release manifest schema or SHA is invalid")
    if set(data["images"]) != IMAGE_NAMES:
        raise ValueError("release manifest must contain django, next, and edge images")
    for name, image in data["images"].items():
        if not isinstance(image, str) or not DIGEST_IMAGE.fullmatch(image):
            raise ValueError(f"{name} image is not pinned by a sha256 digest")
        if ":latest" in image or image.endswith("@" + "sha256:" + "0" * 64):
            raise ValueError(
                f"{name} image uses a forbidden placeholder or mutable tag"
            )
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expect-sha")
    args = parser.parse_args()
    try:
        data = load_manifest(args.manifest)
        if args.expect_sha and data["release_sha"] != args.expect_sha:
            raise ValueError(
                "release manifest SHA does not match the requested release"
            )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"invalid release manifest: {error}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
