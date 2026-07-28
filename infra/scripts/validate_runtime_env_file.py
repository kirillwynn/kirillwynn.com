#!/usr/bin/env python3
"""Validate and atomically install a directory of role-scoped raw env files."""

import argparse
import os
import shutil
import tempfile
from pathlib import Path

from env_value import values
from render_runtime_env import (
    ENVIRONMENT_RULES,
    OPTIONAL_INPUTS,
    ROLE_FIELDS,
    validate_environment_identity,
    validate_value,
)


def validated_directory(environment, source):
    expected_files = set(ROLE_FIELDS)
    actual_files = {path.name for path in source.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise ValueError(
            "runtime environment files invalid; "
            f"unexpected={sorted(actual_files - expected_files)}, "
            f"missing={sorted(expected_files - actual_files)}"
        )
    parsed = {}
    combined = {}
    for filename, allowed in ROLE_FIELDS.items():
        role_values = values(source / filename)
        required = allowed - (OPTIONAL_INPUTS if filename == "worker.env" else set())
        unexpected = sorted(set(role_values) - allowed)
        missing = sorted(required - set(role_values))
        if unexpected or missing:
            raise ValueError(
                f"{filename} shape invalid; unexpected={unexpected}, missing={missing}"
            )
        for name, value in role_values.items():
            validate_value(name, value)
            if name != "SERVICE_ROLE" and name in combined and combined[name] != value:
                raise ValueError(f"{name} differs across role files")
            if name != "SERVICE_ROLE":
                combined[name] = value
        parsed[filename] = role_values
    if parsed["django.env"]["SERVICE_ROLE"] != "web":
        raise ValueError("django.env SERVICE_ROLE must be web")
    if parsed["worker.env"]["SERVICE_ROLE"] != "worker":
        raise ValueError("worker.env SERVICE_ROLE must be worker")
    if any(
        name in parsed["next.env"]
        for name in (
            "POSTGRES_PASSWORD",
            "DJANGO_SECRET_KEY",
            "S3_MEDIA_SECRET_ACCESS_KEY",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GITHUB_OAUTH_CLIENT_SECRET",
            "RESEND_API_KEY",
            "RESEND_WEBHOOK_SECRET",
        )
    ):
        raise ValueError("next.env contains a server secret")
    validate_environment_identity(environment, combined)
    return parsed


def install_directory(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.umask(0o077)
    temporary = Path(
        tempfile.mkdtemp(dir=destination.parent, prefix=f".{destination.name}.")
    )
    try:
        for filename in sorted(ROLE_FIELDS):
            shutil.copyfile(source / filename, temporary / filename)
            os.chmod(temporary / filename, 0o600)
            descriptor = os.open(temporary / filename, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        os.chmod(temporary, 0o700)
        descriptor = os.open(temporary, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if destination.exists():
            raise ValueError(f"runtime release directory already exists: {destination}")
        os.replace(temporary, destination)
        descriptor = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment", choices=sorted(ENVIRONMENT_RULES), required=True
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        validated_directory(args.environment, args.input_dir)
        install_directory(args.input_dir, args.output_dir)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
