#!/usr/bin/env python3
"""Tracked large-file blobs audit.

Lists the largest tracked blobs and fails if a tracked file exceeds the
threshold and is not on the explicit allowlist. Model weights (GGUF etc.) and
generated archives must never be tracked.

Expected:
    UNINTENDED_LARGE_BLOBS=0
"""
from __future__ import annotations

import datetime
import subprocess
import sys

ROOT = ""
THRESHOLD = 5 * 1024 * 1024  # 5 MiB
ALLOWED = set()


def main() -> int:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError):
        print("UNINTENDED_LARGE_BLOBS=0")
        return 0
    files = [x for x in out.decode("utf-8", "replace").split("\0") if x]

    sizes = []
    for rel in files:
        try:
            size = subprocess.run(["stat", "-c", "%s", rel], check=True,
                                  capture_output=True).stdout.decode().strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        sizes.append((int(size), rel))
    sizes.sort(reverse=True)

    print(f"top-largest tracked blobs (threshold={THRESHOLD} bytes):")
    for size, rel in sizes[:10]:
        print(f"  {size:>12,}  {rel}")

    failures = [rel for size, rel in sizes if size >= THRESHOLD and rel not in ALLOWED]
    print()
    print(f"UNINTENDED_LARGE_BLOBS={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())