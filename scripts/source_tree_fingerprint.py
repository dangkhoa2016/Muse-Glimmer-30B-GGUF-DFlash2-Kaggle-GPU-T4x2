#!/usr/bin/env python3
"""Deterministic SHA256 fingerprint for a llama.cpp source tree."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path

EXCLUDE_DIR_NAMES = {'.git', '__pycache__'}
EXCLUDE_PREFIXES = ('build', 'cmake-build')
EXCLUDE_SUFFIXES = {'.pyc', '.pyo'}


def included(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:
        if part in EXCLUDE_DIR_NAMES or any(part.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            return False
    return path.suffix not in EXCLUDE_SUFFIXES


def fingerprint(root: Path) -> str:
    h = hashlib.sha256()
    files = sorted((p for p in root.rglob('*') if p.is_file() and included(p, root)), key=lambda p: p.relative_to(root).as_posix())
    for path in files:
        rel = path.relative_to(root).as_posix().encode()
        h.update(len(rel).to_bytes(4, 'big'))
        h.update(rel)
        file_hash = hashlib.sha256(path.read_bytes()).digest()
        h.update(file_hash)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    args = ap.parse_args()
    print(fingerprint(Path(args.root).resolve()))


if __name__ == '__main__':
    main()
