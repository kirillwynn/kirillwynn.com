#!/usr/bin/env python3
import argparse
import os
import re
import tempfile
from pathlib import Path

COMMON = {
    "RELEASE_SHA",
    "POSTGRES_IMAGE",
    "EDGE_NETWORK",
    "DJANGO_EDGE_ALIAS",
    "NEXT_EDGE_ALIAS",
    "RUNTIME_ENV_FILE",
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
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
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
    "RESEND_API_KEY",
    "RESEND_WEBHOOK_SECRET",
    "WORKER_PUBLISH_INTERVAL_SECONDS",
    "WORKER_REVALIDATION_INTERVAL_SECONDS",
    "WORKER_EMAIL_INTERVAL_SECONDS",
    "WORKER_WEBHOOK_INTERVAL_SECONDS",
    "WORKER_REVALIDATION_BATCH_SIZE",
    "WORKER_EMAIL_OUTBOX_BATCH_SIZE",
    "WORKER_EMAIL_DELIVERY_BATCH_SIZE",
    "WORKER_WEBHOOK_BATCH_SIZE",
}
REQUIRED = COMMON - {
    "WORKER_PUBLISH_INTERVAL_SECONDS",
    "WORKER_REVALIDATION_INTERVAL_SECONDS",
    "WORKER_EMAIL_INTERVAL_SECONDS",
    "WORKER_WEBHOOK_INTERVAL_SECONDS",
    "WORKER_REVALIDATION_BATCH_SIZE",
    "WORKER_EMAIL_OUTBOX_BATCH_SIZE",
    "WORKER_EMAIL_DELIVERY_BATCH_SIZE",
    "WORKER_WEBHOOK_BATCH_SIZE",
}
ENVIRONMENT_RULES = {
    "staging": {
        "host": "staging.kirillwynn.com",
        "database": re.compile(r".*staging.*"),
        "database_user": re.compile(r".*staging.*"),
        "prefix": re.compile(r"(^|/)staging(/|$)"),
        "bucket": re.compile(r".*staging.*"),
        "provider_namespace": re.compile(r"(^|/)staging(/|$)"),
        "edge_network": "kirillwynn-staging-edge",
        "django_alias": "staging-django",
        "next_alias": "staging-next",
        "runtime_file": "/srv/kirillwynn/runtime/staging.env",
    },
    "production": {
        "host": "kirillwynn.com",
        "database": re.compile(r".*production.*"),
        "database_user": re.compile(r".*production.*"),
        "prefix": re.compile(r"(^|/)production(/|$)"),
        "bucket": re.compile(r".*production.*"),
        "provider_namespace": re.compile(r"(^|/)production(/|$)"),
        "edge_network": "kirillwynn-production-edge",
        "django_alias": "production-django",
        "next_alias": "production-next",
        "runtime_file": "/srv/kirillwynn/runtime/production.env",
    },
}
DIGEST_REFERENCE = re.compile(r"^[^@\s]+@sha256:([0-9a-f]{64})$")


def validate_environment_identity(environment, values):
    rules = ENVIRONMENT_RULES[environment]
    checks = (
        ("DJANGO_ALLOWED_HOSTS", values["DJANGO_ALLOWED_HOSTS"] == rules["host"]),
        ("POSTGRES_DB", bool(rules["database"].fullmatch(values["POSTGRES_DB"]))),
        (
            "POSTGRES_USER",
            bool(rules["database_user"].fullmatch(values["POSTGRES_USER"])),
        ),
        ("S3_MEDIA_PREFIX", bool(rules["prefix"].search(values["S3_MEDIA_PREFIX"]))),
        ("S3_MEDIA_BUCKET", bool(rules["bucket"].fullmatch(values["S3_MEDIA_BUCKET"]))),
        (
            "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE",
            bool(
                rules["provider_namespace"].search(
                    values["EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE"]
                )
            ),
        ),
        ("EDGE_NETWORK", values["EDGE_NETWORK"] == rules["edge_network"]),
        ("DJANGO_EDGE_ALIAS", values["DJANGO_EDGE_ALIAS"] == rules["django_alias"]),
        ("NEXT_EDGE_ALIAS", values["NEXT_EDGE_ALIAS"] == rules["next_alias"]),
        ("RUNTIME_ENV_FILE", values["RUNTIME_ENV_FILE"] == rules["runtime_file"]),
    )
    for name, valid in checks:
        if not valid:
            raise ValueError(f"{name} does not identify the selected environment")
    if not re.fullmatch(r"[0-9a-f]{40}", values["RELEASE_SHA"]):
        raise ValueError("RELEASE_SHA must be a full lowercase Git SHA")
    digest_match = DIGEST_REFERENCE.fullmatch(values["POSTGRES_IMAGE"])
    if not digest_match or digest_match.group(1) == "0" * 64:
        raise ValueError("POSTGRES_IMAGE must use a non-zero immutable digest")


def validated_values(environment):
    missing = sorted(name for name in REQUIRED if not os.environ.get(name, "").strip())
    if missing:
        raise ValueError("missing required runtime names: " + ", ".join(missing))
    values = {}
    for name in sorted(COMMON):
        value = os.environ.get(name)
        if value is None:
            continue
        if "\n" in value or "\r" in value or "\0" in value or len(value) > 8192:
            raise ValueError(f"{name} is not a bounded single-line value")
        values[name] = value
    validate_environment_identity(environment, values)
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment", choices=sorted(ENVIRONMENT_RULES), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    values = validated_values(args.environment)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.umask(0o077)
    descriptor, temporary = tempfile.mkstemp(
        dir=args.output.parent,
        prefix=f".{args.output.name}.",
    )
    try:
        with os.fdopen(descriptor, "w") as handle:
            for name, value in values.items():
                handle.write(f"{name}={value}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, args.output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == "__main__":
    main()
