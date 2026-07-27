#!/usr/bin/env python3
import argparse
from pathlib import Path

from validate_release_manifest import IMAGE_NAMES, load_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("image", choices=sorted(IMAGE_NAMES))
    args = parser.parse_args()
    print(load_manifest(args.manifest)["images"][args.image], end="")


if __name__ == "__main__":
    main()
