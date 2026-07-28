#!/usr/bin/env python3
"""Render role-scoped Compose env files without quoting or interpolation.

Docker Compose 2.30+ reads these files with ``env_file.format: raw``. Values
are written byte-for-byte after rejecting line-oriented format hazards.
"""

import argparse
import os
import re
import tempfile
from pathlib import Path

MAX_VALUE_BYTES = 8192
DIGEST_REFERENCE = re.compile(r"^[^@\s]+@sha256:([0-9a-f]{64})$")

CONTROL_FIELDS = {
    "COMPOSE_PROJECT_NAME",
    "ENVIRONMENT",
    "RELEASE_SHA",
    "DEPLOY_SEQUENCE",
    "POSTGRES_IMAGE",
    "DJANGO_IMAGE",
    "NEXT_IMAGE",
    "POSTGRES_ENV_FILE",
    "DJANGO_ENV_FILE",
    "WORKER_ENV_FILE",
    "NEXT_ENV_FILE",
    "DATABASE_NETWORK",
    "APPLICATION_NETWORK",
    "EGRESS_NETWORK",
    "EDGE_NETWORK",
    "POSTGRES_VOLUME",
    "NEXT_CACHE_VOLUME",
    "DJANGO_EDGE_ALIAS",
    "NEXT_EDGE_ALIAS",
}
POSTGRES_FIELDS = {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"}
DJANGO_FIELDS = {
    "SERVICE_ROLE",
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "WAGTAIL_ADMIN_BASE_URL",
    "PUBLIC_SITE_URL",
    "FRONTEND_PREVIEW_URL",
    "REVALIDATION_URL",
    "REVALIDATION_SECRET",
    "SUBSCRIPTION_SIGNING_SECRET",
    "POSTGRES_SSLMODE",
    "S3_MEDIA_ACCESS_KEY_ID",
    "S3_MEDIA_SECRET_ACCESS_KEY",
    "S3_MEDIA_BUCKET",
    "S3_MEDIA_PREFIX",
    "S3_MEDIA_ENDPOINT_URL",
    "S3_MEDIA_REGION",
    "S3_MEDIA_ADDRESSING_STYLE",
    "S3_MEDIA_PUBLIC_ORIGIN",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GITHUB_OAUTH_CLIENT_ID",
    "GITHUB_OAUTH_CLIENT_SECRET",
    "EMAIL_PROVIDER_ADAPTER",
    "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE",
    "EMAIL_FROM_ADDRESS",
    "RESEND_WEBHOOK_SECRET",
}
WORKER_FIELDS = {
    "SERVICE_ROLE",
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_SECRET_KEY",
    "PUBLIC_SITE_URL",
    "REVALIDATION_URL",
    "REVALIDATION_SECRET",
    "SUBSCRIPTION_SIGNING_SECRET",
    "POSTGRES_SSLMODE",
    "S3_MEDIA_ACCESS_KEY_ID",
    "S3_MEDIA_SECRET_ACCESS_KEY",
    "S3_MEDIA_BUCKET",
    "S3_MEDIA_PREFIX",
    "S3_MEDIA_ENDPOINT_URL",
    "S3_MEDIA_REGION",
    "S3_MEDIA_ADDRESSING_STYLE",
    "S3_MEDIA_PUBLIC_ORIGIN",
    "EMAIL_PROVIDER_ADAPTER",
    "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE",
    "EMAIL_FROM_ADDRESS",
    "RESEND_API_KEY",
    "RESEND_API_URL",
    "WORKER_EGRESS_PROBE_URL",
    "WORKER_PUBLISH_INTERVAL_SECONDS",
    "WORKER_REVALIDATION_INTERVAL_SECONDS",
    "WORKER_EMAIL_INTERVAL_SECONDS",
    "WORKER_WEBHOOK_INTERVAL_SECONDS",
    "WORKER_REVALIDATION_BATCH_SIZE",
    "WORKER_EMAIL_OUTBOX_BATCH_SIZE",
    "WORKER_EMAIL_DELIVERY_BATCH_SIZE",
    "WORKER_WEBHOOK_BATCH_SIZE",
}
NEXT_FIELDS = {"PUBLIC_SITE_URL", "DJANGO_API_URL", "REVALIDATION_SECRET"}
ROLE_FIELDS = {
    "control.env": CONTROL_FIELDS,
    "postgres.env": POSTGRES_FIELDS,
    "django.env": DJANGO_FIELDS,
    "worker.env": WORKER_FIELDS,
    "next.env": NEXT_FIELDS,
}
OPTIONAL_INPUTS = {
    "WORKER_PUBLISH_INTERVAL_SECONDS",
    "WORKER_REVALIDATION_INTERVAL_SECONDS",
    "WORKER_EMAIL_INTERVAL_SECONDS",
    "WORKER_WEBHOOK_INTERVAL_SECONDS",
    "WORKER_REVALIDATION_BATCH_SIZE",
    "WORKER_EMAIL_OUTBOX_BATCH_SIZE",
    "WORKER_EMAIL_DELIVERY_BATCH_SIZE",
    "WORKER_WEBHOOK_BATCH_SIZE",
}
GENERATED_FIELDS = CONTROL_FIELDS | {
    "SERVICE_ROLE",
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_API_URL",
}
REQUIRED_INPUTS = (
    (POSTGRES_FIELDS | DJANGO_FIELDS | WORKER_FIELDS | NEXT_FIELDS)
    - GENERATED_FIELDS
    - OPTIONAL_INPUTS
)
# Backward-compatible name used by infrastructure unit tests.
REQUIRED = REQUIRED_INPUTS

ENVIRONMENT_RULES = {
    "staging": {
        "host": "staging.kirillwynn.com",
        "database": re.compile(r".*staging.*"),
        "database_user": re.compile(r".*staging.*"),
        "prefix": re.compile(r"(^|/)staging(/|$)"),
        "provider_namespace": re.compile(r"(^|/)staging(/|$)"),
    },
    "production": {
        "host": "kirillwynn.com",
        "database": re.compile(r".*production.*"),
        "database_user": re.compile(r".*production.*"),
        "prefix": re.compile(r"(^|/)production(/|$)"),
        "provider_namespace": re.compile(r"(^|/)production(/|$)"),
    },
}


def validate_value(name, value):
    if not isinstance(value, str):
        raise ValueError(f"{name} is not a string")
    if "\n" in value or "\r" in value or "\0" in value:
        raise ValueError(f"{name} is not a single-line NUL-free value")
    if len(value.encode()) > MAX_VALUE_BYTES:
        raise ValueError(f"{name} exceeds {MAX_VALUE_BYTES} bytes")


def validate_environment_identity(environment, values):
    rules = ENVIRONMENT_RULES[environment]
    host = rules["host"]
    runtime_root = f"/srv/kirillwynn/runtime/releases/{values.get('RELEASE_SHA', '')}/{environment}"
    expected = {
        "COMPOSE_PROJECT_NAME": f"kirillwynn-{environment}",
        "ENVIRONMENT": environment,
        "DATABASE_NETWORK": f"kirillwynn-{environment}-database",
        "APPLICATION_NETWORK": f"kirillwynn-{environment}-application",
        "EGRESS_NETWORK": f"kirillwynn-{environment}-egress",
        "EDGE_NETWORK": f"kirillwynn-{environment}-edge",
        "POSTGRES_VOLUME": f"kirillwynn-{environment}-postgres",
        "NEXT_CACHE_VOLUME": f"kirillwynn-{environment}-next-cache",
        "DJANGO_EDGE_ALIAS": f"{environment}-django",
        "NEXT_EDGE_ALIAS": f"{environment}-next",
        "POSTGRES_ENV_FILE": f"{runtime_root}/postgres.env",
        "DJANGO_ENV_FILE": f"{runtime_root}/django.env",
        "WORKER_ENV_FILE": f"{runtime_root}/worker.env",
        "NEXT_ENV_FILE": f"{runtime_root}/next.env",
    }
    for name, expected_value in expected.items():
        if values.get(name) != expected_value:
            raise ValueError(f"{name} does not identify the selected environment")
    checks = (
        (
            "DJANGO_ALLOWED_HOSTS",
            values["DJANGO_ALLOWED_HOSTS"] == f"{host},django,127.0.0.1",
        ),
        ("POSTGRES_DB", bool(rules["database"].fullmatch(values["POSTGRES_DB"]))),
        (
            "POSTGRES_USER",
            bool(rules["database_user"].fullmatch(values["POSTGRES_USER"])),
        ),
        ("S3_MEDIA_PREFIX", bool(rules["prefix"].search(values["S3_MEDIA_PREFIX"]))),
        (
            "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE",
            bool(
                rules["provider_namespace"].search(
                    values["EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE"]
                )
            ),
        ),
    )
    for name, valid in checks:
        if not valid:
            raise ValueError(f"{name} does not identify the selected environment")
    if not re.fullmatch(r"[0-9a-f]{40}", values["RELEASE_SHA"]):
        raise ValueError("RELEASE_SHA must be a full lowercase Git SHA")
    if not values["DEPLOY_SEQUENCE"].isdigit():
        raise ValueError("DEPLOY_SEQUENCE must be an unsigned integer")
    for name in ("POSTGRES_IMAGE", "DJANGO_IMAGE", "NEXT_IMAGE"):
        digest_match = DIGEST_REFERENCE.fullmatch(values[name])
        if not digest_match or digest_match.group(1) == "0" * 64:
            raise ValueError(f"{name} must use a non-zero immutable digest")


def runtime_values(environment):
    missing = sorted(
        name
        for name in REQUIRED_INPUTS
        if os.environ.get(name) is None or not os.environ[name]
    )
    if missing:
        raise ValueError("missing required runtime names: " + ", ".join(missing))
    release_sha = os.environ.get("RELEASE_SHA", "")
    deploy_sequence = os.environ.get("DEPLOY_SEQUENCE", "")
    runtime_root = f"/srv/kirillwynn/runtime/releases/{release_sha}/{environment}"
    control = {
        "COMPOSE_PROJECT_NAME": f"kirillwynn-{environment}",
        "ENVIRONMENT": environment,
        "RELEASE_SHA": release_sha,
        "DEPLOY_SEQUENCE": deploy_sequence,
        "POSTGRES_IMAGE": os.environ.get("POSTGRES_IMAGE", ""),
        "DJANGO_IMAGE": os.environ.get("DJANGO_IMAGE", ""),
        "NEXT_IMAGE": os.environ.get("NEXT_IMAGE", ""),
        "POSTGRES_ENV_FILE": f"{runtime_root}/postgres.env",
        "DJANGO_ENV_FILE": f"{runtime_root}/django.env",
        "WORKER_ENV_FILE": f"{runtime_root}/worker.env",
        "NEXT_ENV_FILE": f"{runtime_root}/next.env",
        "DATABASE_NETWORK": f"kirillwynn-{environment}-database",
        "APPLICATION_NETWORK": f"kirillwynn-{environment}-application",
        "EGRESS_NETWORK": f"kirillwynn-{environment}-egress",
        "EDGE_NETWORK": f"kirillwynn-{environment}-edge",
        "POSTGRES_VOLUME": f"kirillwynn-{environment}-postgres",
        "NEXT_CACHE_VOLUME": f"kirillwynn-{environment}-next-cache",
        "DJANGO_EDGE_ALIAS": f"{environment}-django",
        "NEXT_EDGE_ALIAS": f"{environment}-next",
    }
    postgres = {name: os.environ[name] for name in POSTGRES_FIELDS}
    django = {
        name: (
            "web"
            if name == "SERVICE_ROLE"
            else "config.settings.production"
            if name == "DJANGO_SETTINGS_MODULE"
            else f"{os.environ[name]},django,127.0.0.1"
            if name == "DJANGO_ALLOWED_HOSTS"
            else os.environ[name]
        )
        for name in DJANGO_FIELDS
    }
    worker = {
        name: (
            "worker"
            if name == "SERVICE_ROLE"
            else "config.settings.production"
            if name == "DJANGO_SETTINGS_MODULE"
            else os.environ[name]
        )
        for name in WORKER_FIELDS
        if name not in OPTIONAL_INPUTS or name in os.environ
    }
    next_values = {
        "PUBLIC_SITE_URL": os.environ["PUBLIC_SITE_URL"],
        "DJANGO_API_URL": "http://django:8000",
        "REVALIDATION_SECRET": os.environ["REVALIDATION_SECRET"],
    }
    roles = {
        "control.env": control,
        "postgres.env": postgres,
        "django.env": django,
        "worker.env": worker,
        "next.env": next_values,
    }
    combined = {}
    for values in roles.values():
        for name, value in values.items():
            validate_value(name, value)
            combined.setdefault(name, value)
    validate_environment_identity(environment, combined)
    return roles


def write_raw_environment(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    os.umask(0o077)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", newline="\n") as handle:
            for name in sorted(values):
                handle.write(f"{name}={values[name]}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment", choices=sorted(ENVIRONMENT_RULES), required=True
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        roles = runtime_values(args.environment)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    for filename, values in roles.items():
        write_raw_environment(args.output_dir / filename, values)


if __name__ == "__main__":
    main()
