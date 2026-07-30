#!/usr/bin/env python3
"""Safely extract one bounded private reaction-catalog transfer archive."""

import argparse
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath

MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_EXTRACTED_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = 512 * 1024
MAX_MEMBERS = 300
CATALOG_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SHA256 = re.compile(r"[0-9a-f]{64}")
OBJECT_NAMES = {"animation.gif", "asset.webp", "poster.webp"}


def checked_path(name: str) -> PurePosixPath:
    if not name or "\\" in name:
        raise ValueError("archive member path is empty or non-POSIX")
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or path.as_posix() != name
    ):
        raise ValueError(f"unsafe archive member path: {name!r}")
    return path


def allowed_file(path: PurePosixPath) -> bool:
    if path == PurePosixPath("reaction-catalog-attestation.json"):
        return True
    parts = path.parts
    return (
        len(parts) == 5
        and parts[:2] == ("objects", "reactions")
        and CATALOG_ID.fullmatch(parts[2]) is not None
        and SHA256.fullmatch(parts[3]) is not None
        and parts[4] in OBJECT_NAMES
    )


def extract(archive_path: Path, output_directory: Path) -> None:
    archive_path = archive_path.resolve(strict=True)
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("catalog transfer archive exceeds the 16 MiB limit")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise ValueError("catalog transfer output directory must be empty")
    output_directory.mkdir(parents=True, exist_ok=True)
    output_directory = output_directory.resolve(strict=True)

    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        if not 2 <= len(members) <= MAX_MEMBERS:
            raise ValueError("catalog transfer member count is outside the safe range")
        names: set[str] = set()
        total_size = 0
        file_count = 0
        for member in members:
            path = checked_path(member.name)
            if member.name in names:
                raise ValueError(f"duplicate archive member: {member.name!r}")
            names.add(member.name)
            if member.isdir():
                raise ValueError(f"directory entries are not allowed: {member.name!r}")
            if not member.isfile():
                raise ValueError(f"non-regular archive member: {member.name!r}")
            if not allowed_file(path):
                raise ValueError(f"unexpected catalog transfer member: {member.name!r}")
            if member.size < 0 or member.size > MAX_FILE_BYTES:
                raise ValueError(
                    f"catalog transfer member is too large: {member.name!r}"
                )
            total_size += member.size
            file_count += 1
        if total_size > MAX_EXTRACTED_BYTES:
            raise ValueError("catalog transfer extracted size exceeds the 16 MiB limit")
        if file_count < 2:
            raise ValueError("catalog transfer must contain attestation and objects")
        if "reaction-catalog-attestation.json" not in names:
            raise ValueError("catalog transfer attestation is missing")

        for member in members:
            path = checked_path(member.name)
            destination = output_directory.joinpath(*path.parts)
            try:
                destination.relative_to(output_directory)
            except ValueError as error:
                raise ValueError(
                    "catalog transfer escaped its output directory"
                ) from error
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(
                    f"catalog transfer member has no body: {member.name!r}"
                )
            with source, destination.open("xb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            if destination.stat().st_size != member.size:
                raise ValueError(
                    f"catalog transfer member is truncated: {member.name!r}"
                )
            destination.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    try:
        extract(args.archive, args.output_directory)
    except (OSError, tarfile.TarError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
