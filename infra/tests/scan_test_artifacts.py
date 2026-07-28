#!/usr/bin/env python3
"""Fail-closed scanner for Playwright artifacts retained by CI."""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from collections.abc import Iterable
from pathlib import Path

DENYLIST = re.compile(
    rb"django sentinel|postgres sentinel|s3-only-integration-secret|"
    rb"google-only-integration-secret|github-only-integration-secret|"
    rb"revalidation sentinel|production-check-only|"
    rb"https?://(django|postgres|db|minio|worker|outbox|next|edge)(:[0-9]+)?|"
    rb"authorization\s*:\s*bearer|(set-)?cookie\s*:|sessionid=|csrftoken=|"
    rb"kw_preview_credential=|e2e_provider=|deterministic-test-csrf|"
    rb"e2e-(preview|confirm|unsubscribe)|"
    rb"(DJANGO_SECRET_KEY|DJANGO_API_URL|REVALIDATION_SECRET|RESEND_API_KEY|"
    rb"RESEND_WEBHOOK_SECRET|SUBSCRIPTION_SIGNING_SECRET|POSTGRES_PASSWORD|"
    rb"S3_MEDIA_SECRET_ACCESS_KEY|OAUTH_CLIENT_SECRET)\s*[:=]",
    re.IGNORECASE,
)

PLAIN_SUFFIXES = {
    ".css",
    ".html",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".png",
    ".txt",
    ".webp",
    ".xml",
}
ZIP_SUFFIXES = {".zip"}
MAX_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


class ScanFailure(RuntimeError):
    """The retained set could not be proven safe."""


def _fault(name: str) -> None:
    """Deterministic operational failure injection used by regression tests."""

    if os.environ.get("ARTIFACT_SCANNER_INJECT_FAILURE") == name:
        raise ScanFailure(f"injected {name} failure")


def discover(root: Path) -> list[Path]:
    _fault("find")
    try:
        return sorted(path for path in root.rglob("*") if path.is_file())
    except OSError as error:
        raise ScanFailure(f"cannot enumerate retained artifacts: {error}") from error


def _read_plain(path: Path) -> bytes:
    _fault("read")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ScanFailure(f"cannot read retained artifact {path}: {error}") from error


def _zip_payloads(path: Path) -> Iterable[tuple[str, bytes]]:
    _fault("unzip")
    try:
        with zipfile.ZipFile(path) as archive:
            bad_entry = archive.testzip()
            if bad_entry is not None:
                raise ScanFailure(f"corrupt ZIP entry {bad_entry!r} in {path}")
            entries = archive.infolist()
            if not entries:
                raise ScanFailure(f"empty ZIP artifact has unknown retained content: {path}")
            if sum(entry.file_size for entry in entries) > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ScanFailure(f"ZIP artifact exceeds the inspection limit: {path}")
            for entry in entries:
                if entry.is_dir():
                    continue
                if entry.flag_bits & 0x1:
                    raise ScanFailure(f"encrypted ZIP entry {entry.filename!r} in {path}")
                try:
                    yield entry.filename, archive.read(entry)
                except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                    raise ScanFailure(
                        f"cannot read ZIP entry {entry.filename!r} in {path}: {error}"
                    ) from error
    except ScanFailure:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise ScanFailure(f"cannot inspect ZIP artifact {path}: {error}") from error


def is_unsafe(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in PLAIN_SUFFIXES:
        return DENYLIST.search(_read_plain(path)) is not None
    if suffix in ZIP_SUFFIXES:
        return any(DENYLIST.search(payload) is not None for _, payload in _zip_payloads(path))
    raise ScanFailure(f"unknown retained artifact format: {path}")


def remove(path: Path) -> None:
    _fault("remove")
    try:
        path.unlink()
    except OSError as error:
        raise ScanFailure(f"cannot remove unsafe retained artifact {path}: {error}") from error


def scan(root: Path, *, remove_unsafe: bool) -> None:
    if not root.exists():
        return
    if not root.is_dir():
        raise ScanFailure(f"artifact root is not a directory: {root}")

    for artifact in discover(root):
        if not is_unsafe(artifact):
            continue
        if not remove_unsafe:
            raise ScanFailure(
                f"retained artifact contains a forbidden byte pattern: {artifact}"
            )
        print(f"Removing unsafe retained artifact before upload: {artifact}", file=sys.stderr)
        remove(artifact)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove-unsafe", action="store_true")
    parser.add_argument("artifact_root", type=Path)
    args = parser.parse_args()
    try:
        scan(args.artifact_root, remove_unsafe=args.remove_unsafe)
    except ScanFailure as error:
        print(f"Artifact scan failed closed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
