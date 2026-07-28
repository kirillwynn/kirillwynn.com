#!/usr/bin/env python3
"""Fail-closed scanner for Playwright artifacts retained by CI."""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import BinaryIO

DENYLIST = re.compile(
    rb"django sentinel|postgres sentinel|s3-only-integration-secret|"
    rb"google-only-integration-secret|github-only-integration-secret|"
    rb"revalidation sentinel|production-check-only|"
    rb"https?://(django|postgres|db|minio|worker|outbox|next|edge)(:[0-9]+)?|"
    rb"(?:authorization|cookie|set-cookie)\s*:|"
    rb"[\"']name[\"']\s*:\s*[\"'](?:authorization|cookie|set-cookie)[\"']|"
    rb"[\"'](?:authorization|cookie|set-cookie)[\"']\s*:\s*[\"']|"
    rb"[\"']name[\"']\s*:\s*[\"'](?:__Host-)?"
    rb"(?:sessionid|csrftoken|kw_preview_credential)[\"']|"
    rb"[\"'](?:__Host-)?(?:sessionid|csrftoken|kw_preview_credential)[\"']"
    rb"\s*:\s*[\"']|"
    rb"(?:__Host-)?(?:sessionid|csrftoken|kw_preview_credential)=|"
    rb"(?:[?&#]|%3[fF]|%23|%26)"
    rb"(?:credential|access_token|refresh_token|code|kw_preview_credential)"
    rb"(?:=|%3[dD])|"
    rb"(?:^|&)(?:credential|access_token|refresh_token|code)=|"
    rb"[\"'](?:credential|access_token|refresh_token|authorization_code|code)"
    rb"[\"']\s*:\s*[\"'][^\"']+|"
    rb"provider-boundary-(?:code|access-token|refresh-token)|"
    rb"[A-Za-z0-9_-]{32,}:[A-Za-z0-9]+:[A-Za-z0-9_-]{20,}|"
    rb"e2e_provider=|deterministic-test-csrf|"
    rb"e2e-(preview|confirm|unsubscribe)|"
    rb"(DJANGO_SECRET_KEY|DJANGO_API_URL|REVALIDATION_SECRET|RESEND_API_KEY|"
    rb"RESEND_WEBHOOK_SECRET|SUBSCRIPTION_SIGNING_SECRET|POSTGRES_PASSWORD|"
    rb"S3_MEDIA_SECRET_ACCESS_KEY|OAUTH_CLIENT_SECRET)[\"']?\s*[:=]",
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
READ_CHUNK_BYTES = 64 * 1024
SCAN_OVERLAP_BYTES = 8 * 1024
MAX_PLAIN_ARTIFACT_BYTES = 100 * 1024 * 1024
MAX_ZIP_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_ENTRY_BYTES = 100 * 1024 * 1024
MAX_ZIP_COMPRESSED_BYTES = 100 * 1024 * 1024
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


def _declared_size(path: Path, *, limit: int, kind: str) -> int:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ScanFailure(f"cannot stat {kind} {path}: {error}") from error
    if size > limit:
        raise ScanFailure(f"{kind} exceeds the inspection limit: {path}")
    return size


def _stream_is_unsafe(
    source: BinaryIO,
    *,
    byte_limit: int,
    description: str,
) -> tuple[bool, int]:
    scanned = 0
    overlap = b""
    while True:
        try:
            chunk = source.read(READ_CHUNK_BYTES)
        except (
            EOFError,
            NotImplementedError,
            OSError,
            RuntimeError,
            ValueError,
            zipfile.BadZipFile,
        ) as error:
            raise ScanFailure(f"cannot read {description}: {error}") from error
        if not chunk:
            return False, scanned
        scanned += len(chunk)
        if scanned > byte_limit:
            raise ScanFailure(f"{description} exceeds the inspection limit")
        window = overlap + chunk
        if DENYLIST.search(window) is not None:
            return True, scanned
        overlap = window[-SCAN_OVERLAP_BYTES:]


def _plain_is_unsafe(path: Path) -> bool:
    _fault("read")
    _declared_size(path, limit=MAX_PLAIN_ARTIFACT_BYTES, kind="plain artifact")
    try:
        with path.open("rb") as artifact:
            unsafe, _ = _stream_is_unsafe(
                artifact,
                byte_limit=MAX_PLAIN_ARTIFACT_BYTES,
                description=f"retained artifact {path}",
            )
            return unsafe
    except ScanFailure:
        raise
    except OSError as error:
        raise ScanFailure(f"cannot read retained artifact {path}: {error}") from error


def _zip_is_unsafe(path: Path) -> bool:
    _fault("unzip")
    _declared_size(path, limit=MAX_ZIP_ARCHIVE_BYTES, kind="ZIP artifact")
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries:
                raise ScanFailure(
                    f"empty ZIP artifact has unknown retained content: {path}"
                )
            if len(entries) > MAX_ZIP_ENTRIES:
                raise ScanFailure(f"ZIP artifact has too many entries: {path}")

            declared_compressed_total = 0
            declared_total = 0
            has_file = False
            unsafe_filename = False
            for entry in entries:
                if entry.flag_bits & 0x1:
                    raise ScanFailure(
                        f"encrypted ZIP entry {entry.filename!r} in {path}"
                    )
                if entry.file_size > MAX_ZIP_ENTRY_BYTES:
                    raise ScanFailure(
                        f"ZIP entry {entry.filename!r} exceeds the inspection limit in {path}"
                    )
                declared_compressed_total += entry.compress_size
                if declared_compressed_total > MAX_ZIP_COMPRESSED_BYTES:
                    raise ScanFailure(
                        f"ZIP artifact declares too much compressed data: {path}"
                    )
                declared_total += entry.file_size
                if declared_total > MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise ScanFailure(
                        f"ZIP artifact exceeds the inspection limit: {path}"
                    )
                if entry.is_dir():
                    continue
                has_file = True
                unsafe_filename = unsafe_filename or (
                    DENYLIST.search(
                        entry.filename.encode("utf-8", errors="surrogateescape")
                    )
                    is not None
                )

            if not has_file:
                raise ScanFailure(f"ZIP artifact has no inspectable entries: {path}")
            if unsafe_filename:
                return True

            actual_total = 0
            for entry in entries:
                if entry.is_dir():
                    continue
                try:
                    with archive.open(entry, "r") as payload:
                        unsafe, actual_size = _stream_is_unsafe(
                            payload,
                            byte_limit=min(
                                MAX_ZIP_ENTRY_BYTES,
                                MAX_ZIP_UNCOMPRESSED_BYTES - actual_total,
                            ),
                            description=f"ZIP entry {entry.filename!r} in {path}",
                        )
                except ScanFailure:
                    raise
                except (
                    EOFError,
                    NotImplementedError,
                    OSError,
                    RuntimeError,
                    ValueError,
                    zipfile.BadZipFile,
                ) as error:
                    raise ScanFailure(
                        f"cannot read ZIP entry {entry.filename!r} in {path}: {error}"
                    ) from error
                if unsafe:
                    return True
                actual_total += actual_size
                if actual_total > MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise ScanFailure(
                        f"ZIP artifact exceeds the inspection limit: {path}"
                    )
                if actual_size != entry.file_size:
                    raise ScanFailure(
                        f"ZIP entry {entry.filename!r} size disagrees with its declaration in {path}"
                    )
            return False
    except ScanFailure:
        raise
    except (
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as error:
        raise ScanFailure(f"cannot inspect ZIP artifact {path}: {error}") from error


def is_unsafe(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in PLAIN_SUFFIXES:
        return _plain_is_unsafe(path)
    if suffix in ZIP_SUFFIXES:
        return _zip_is_unsafe(path)
    raise ScanFailure(f"unknown retained artifact format: {path}")


def remove(path: Path) -> None:
    _fault("remove")
    try:
        path.unlink()
    except OSError as error:
        raise ScanFailure(
            f"cannot remove unsafe retained artifact {path}: {error}"
        ) from error


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
        print(
            f"Removing unsafe retained artifact before upload: {artifact}",
            file=sys.stderr,
        )
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
