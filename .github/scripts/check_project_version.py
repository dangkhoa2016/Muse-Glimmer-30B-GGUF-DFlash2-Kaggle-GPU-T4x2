#!/usr/bin/env python3
"""Project-version singleton audit.

Scans tracked files for version-like tokens and classifies them:

    PROJECT_VERSION   the one public project version (1.0.0 / v1.0.0)
    DEPENDENCY_VERSION  package versions pinned in config/requirements.lock
    UNCLASSIFIED       anything else -> FAILURE

Also rejects unqualified internal lineage fragments such as speculative minor
or feature releases, and bare module identifiers outside the public 1.0.x
lineage.

Expected:
    PROJECT_VERSION_SINGLETON=PASS
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_VERSION = "1.0.0"
VERSION_RE = re.compile(r"\bv?1\.\d+\.\d+(?!\.\d)\b")
INTERNAL_FRAGMENT_RE = re.compile(r"\bv1\.[2-9](?![0-9])|\bv1[0-9]{2}\b")

FAILURES: list[str] = []


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                             check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [Path(ROOT, x) for x in out.decode("utf-8", "replace").split("\0") if x]


def pin_versions() -> set[str]:
    pins: set[str] = set()
    lock = ROOT / "config/requirements.lock"
    if not lock.is_file():
        return pins
    for m in re.finditer(r"==([0-9]+(?:\.[0-9]+)*(?:\.[0-9]+)?)", lock.read_text(encoding="utf-8")):
        pins.add(m.group(1))
    return pins


def main() -> int:
    deps = pin_versions()
    for path in tracked_files():
        rel = path.relative_to(ROOT)
        if str(rel).startswith(".github") or str(rel) == "SOURCE_MANIFEST.sha256":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in sorted(set(VERSION_RE.findall(text))):
            if token in ("1.0.0", "v1.0.0"):
                kind = "PROJECT_VERSION"
            elif token in deps:
                kind = "DEPENDENCY_VERSION"
            else:
                kind = "UNCLASSIFIED"
                FAILURES.append(f"{rel}: {token}")
            print(f"{kind:20s} {rel}: {token}")
        for frag in sorted(set(INTERNAL_FRAGMENT_RE.findall(text))):
            FAILURES.append(f"{rel}: internal lineage fragment {frag!r}")
            print(f"{'INTERNAL':26s} {rel}: {frag}")

    version = ROOT.joinpath("VERSION").read_text(encoding="utf-8").strip()
    if version != PUBLIC_VERSION:
        FAILURES.append(f"VERSION={version!r}, expected {PUBLIC_VERSION!r}")

    print()
    print(f"PROJECT_VERSION_SINGLETON={'FAIL' if FAILURES else 'PASS'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())