#!/usr/bin/env python3
import argparse
import os
import tempfile
from pathlib import Path

from env_value import values
from render_runtime_env import (
    ENVIRONMENT_RULES,
    REQUIRED,
    validate_environment_identity,
)

DEPLOYMENT_FIELDS = {
    "RELEASE_SHA",
    "POSTGRES_IMAGE",
    "EDGE_NETWORK",
    "DJANGO_EDGE_ALIAS",
    "NEXT_EDGE_ALIAS",
    "RUNTIME_ENV_FILE",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment", choices=sorted(ENVIRONMENT_RULES), required=True
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    parsed = values(args.input)
    allowed = REQUIRED | DEPLOYMENT_FIELDS
    unexpected = sorted(set(parsed) - allowed)
    missing = sorted((REQUIRED | DEPLOYMENT_FIELDS) - set(parsed))
    if unexpected or missing:
        raise SystemExit(
            f"runtime environment shape invalid; unexpected={unexpected}, missing={missing}"
        )
    try:
        validate_environment_identity(args.environment, parsed)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    os.umask(0o077)
    descriptor, temporary = tempfile.mkstemp(
        dir=args.output.parent,
        prefix=f".{args.output.name}.",
    )
    try:
        with os.fdopen(descriptor, "w") as handle:
            for name in sorted(parsed):
                handle.write(f"{name}={parsed[name]}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, args.output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == "__main__":
    main()
