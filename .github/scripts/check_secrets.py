#!/usr/bin/env python3
"""Secret / privacy scan for tracked files.

Flags common credential and private-data tokens in tracked content and rejects
tracked .env-style files. Never stores a matched value in the report; it prints
only the relative path and the pattern family.

Expected:
    TRACKED_SECRETS=0
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PATTERNS = [
    (r"\bgh[a-z]{5}_[A-Za-z0-9]{20,}\b", "github-token"),
    (r"\bhf_[A-Za-z0-9]{20,}\b", "hf-token"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", "slack-token"),
    (r"\bsk-[A-Za-z0-9]{20,}\b", "api-key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "aws-access-key"),
    (r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b", "jwt"),
    (r"-----BEGIN (?:RSA |OPENSSH |EC |PGP )?PRIVATE KEY-----", "private-key"),
    (r"\b[0-9a-f]{64}\b.{0,60}bearer", "sha-shaped-secret-with-bearer", re.IGNORECASE),
]

FAILURES: list[str] = []


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                             check=True, capture_output=True).stdout
        return [x for x in out.decode("utf-8", "replace").split("\0") if x]
    except (OSError, subprocess.CalledProcessError):
        return []


def main() -> int:
    for rel in sorted(tracked_files()):
        name = Path(rel).name
        if name == ".env" or name.startswith(".env."):
            FAILURES.append(f"{rel}: tracked environment file")
            print(f"SECRET  {rel}: environment-file")
            continue
        text = Path(ROOT, rel).read_text(encoding="utf-8", errors="replace")
        for pattern, label, *flags in PATTERNS:
            if re.search(pattern, text, flags=flags[0] if flags else 0):
                FAILURES.append(f"{rel}: {label}")
                print(f"SECRET  {rel}: {label}")

    print()
    print(f"TRACKED_SECRETS={len(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())