#!/usr/bin/env python3
"""Compare PII-free active and restored Stage 18 staging audit reports."""

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "stage18-staging-data-audit/v1"
SECTIONS = (
    "migrations",
    "identity",
    "posts",
    "discussions",
    "reaction_catalog",
    "subscriptions",
    "auth_email",
    "revalidation",
)
STRICT_PREFIXES = (
    "migrations.",
    "reaction_catalog.",
    "identity.social_tokens",
    "posts.ownerless",
    "posts.public_author_serializer_mismatches",
)


def load_report(path):
    payload = json.loads(path.read_text())
    if payload.get("schema") != SCHEMA:
        raise ValueError(f"{path}: unsupported staging audit schema")
    if not isinstance(payload.get("violations"), dict):
        raise ValueError(f"{path}: violations must be an object")
    for section in SECTIONS:
        if section not in payload:
            raise ValueError(f"{path}: missing {section} section")
    return payload


def flatten(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else key
            result.update(flatten(value[key], path))
        return result
    if isinstance(value, list):
        return {prefix: value}
    if isinstance(value, bool | int | str) or value is None:
        return {prefix: value}
    raise ValueError(f"unsupported value at {prefix}")


def audited_values(report):
    values = {}
    for section in SECTIONS:
        values.update(flatten(report[section], section))
    return values


def compare(before, restored, after):
    before_values = audited_values(before)
    restored_values = audited_values(restored)
    after_values = audited_values(after)
    paths = sorted(set(before_values) | set(restored_values) | set(after_values))
    mismatches = {}
    concurrent_changes = {}
    matched_snapshot_values = 0

    for path in paths:
        values = {
            "before": before_values.get(path),
            "restored": restored_values.get(path),
            "after": after_values.get(path),
        }
        if values["before"] == values["after"]:
            if values["restored"] == values["before"]:
                matched_snapshot_values += 1
            else:
                mismatches[path] = values
            continue

        concurrent_changes[path] = values
        if any(path == prefix or path.startswith(prefix) for prefix in STRICT_PREFIXES):
            mismatches[path] = values

    violation_reports = {
        name: report["violations"]
        for name, report in (
            ("active_before", before),
            ("restored", restored),
            ("active_after", after),
        )
        if report["violations"]
    }
    return {
        "schema": "stage18-staging-data-comparison/v1",
        "matched_snapshot_values": matched_snapshot_values,
        "concurrent_change_count": len(concurrent_changes),
        "concurrent_changes": concurrent_changes,
        "mismatches": mismatches,
        "violation_reports": violation_reports,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("active_before", type=Path)
    parser.add_argument("restored", type=Path)
    parser.add_argument("active_after", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        reports = [
            load_report(args.active_before),
            load_report(args.restored),
            load_report(args.active_after),
        ]
        result = compare(*reports)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(rendered)
        else:
            print(rendered, end="")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"invalid staging data audit: {error}", file=sys.stderr)
        raise SystemExit(2) from None

    if result["mismatches"] or result["violation_reports"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
