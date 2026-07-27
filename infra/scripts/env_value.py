#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def values(path):
    result = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or not NAME.fullmatch(name) or name in result:
            raise ValueError(f"invalid environment entry on line {number}")
        result[name] = value
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("name")
    args = parser.parse_args()
    if not NAME.fullmatch(args.name):
        raise SystemExit("invalid environment name")
    value = values(args.path).get(args.name)
    if value is None:
        raise SystemExit(f"{args.name} is missing")
    print(value, end="")


if __name__ == "__main__":
    main()
