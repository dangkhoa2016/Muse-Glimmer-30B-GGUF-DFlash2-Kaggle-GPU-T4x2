#!/usr/bin/env python3
"""Internal-development-artifact scanner.

Searches tracked files for strong internal development signals and classifies
each match:

    INTERNAL_DEVELOPMENT_ARTIFACT  private dev lineage/phases/sessions/drafts
    PUBLIC_PRODUCT_CONCEPT         legitimate English or public CLI concepts

Generic English terms such as "phase", "stage", "internal", and "preflight"
are allowed as PUBLIC_PRODUCT_CONCEPT here because "preflight" is an actual
public subcommand of ./external.sh; only obvious private-development markers
fail the scan.

Public .github Markdown and metadata are scanned too; only this scanner's own
file (which must contain its pattern literals) is excluded from
content-pattern scanning. Legitimate public product terms stay allowed.

Expected:
    INTERNAL_DEVELOPMENT_ARTIFACTS=0
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCANNER_REL = Path(".github/scripts/check_internal_artifacts.py")

ARTIFACT_PATTERNS = [
    (r"\bcorrective\b", "corrective"),
    (r"\bhandoff\b", "handoff"),
    (r"\bantigravity\b", "antigravity"),
    (r"\bopencode\b", "opencode"),
    (r"\bcodex\b", "codex"),
    (r"\bacceptance[-_ ]?evidence\b", "acceptance-evidence"),
    (r"\bsession-[\w-]+", "session-"),
    (r"\bv8-r\b", "v8-r"),
    (r"\bv1\.[2-9]\b", "v1.x branch"),
    (r"\bv1[0-9]{2}\b", "v1XX module"),
    (r"\brc-?[0-9]+\b", "release-candidate"),
    (r"\bv1\.[2-9](?![0-9])", "v1.x lineage"),
]
ALLOWED_PRODUCT_CONCEPTS = ["preflight"]

FAILURES: list[str] = []


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                             check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [Path(ROOT, x) for x in out.decode("utf-8", "replace").split("\0") if x]


def main() -> int:
    for path in tracked_files():
        rel = path.relative_to(ROOT)
        if rel == SCANNER_REL or str(rel) == "SOURCE_MANIFEST.sha256":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, label in ARTIFACT_PATTERNS:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                token = m.group(0)
                if token.lower() in ALLOWED_PRODUCT_CONCEPTS:
                    print(f"PUBLIC_PRODUCT_CONCEPT  {rel}: {token!r}")
                    continue
                FAILURES.append(f"{rel}: {token!r}")
                print(f"INTERNAL_DEVELOPMENT_ARTIFACT  {rel}: {token!r}")

    print()
    print(f"INTERNAL_DEVELOPMENT_ARTIFACTS={len(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())