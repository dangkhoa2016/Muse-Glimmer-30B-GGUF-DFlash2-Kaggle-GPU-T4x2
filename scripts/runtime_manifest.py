#!/usr/bin/env python3
"""Create and verify provenance manifests for prebuilt llama.cpp Kaggle runtimes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_BINARIES = ("llama-server", "llama-cli", "llama-bench")
SCHEMA_VERSION = 1


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _arches(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        items = value
    else:
        items = value.replace(",", ";").split(";")
    out = []
    for item in items:
        item = str(item).strip()
        if item and item not in out:
            out.append(item)
    return out


def create_manifest(
    bin_dir: Path | str,
    repo: str,
    commit: str,
    cuda_architectures: str | list[str],
    cuda_version: str = "",
) -> dict[str, Any]:
    bin_dir = Path(bin_dir)
    if len(commit) != 40 or any(c not in "0123456789abcdefABCDEF" for c in commit):
        raise ValueError("source commit must be a full 40-character SHA")
    binaries: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_BINARIES:
        path = bin_dir / name
        if not path.is_file():
            raise ValueError(f"required runtime binary missing: {path}")
        binaries[name] = {"size_bytes": path.stat().st_size, "sha256": _sha256(path)}
    arches = _arches(cuda_architectures)
    if not arches:
        raise ValueError("at least one CUDA architecture is required")
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"repo": repo, "commit": commit.lower()},
        "build": {"cuda_architectures": arches, "cuda_version": cuda_version},
        "binaries": binaries,
    }


def verify_manifest(
    manifest_path: Path | str,
    bin_dir: Path | str,
    expected_repo: str,
    expected_commit: str,
    required_cuda_arch: str,
) -> dict[str, Any]:
    manifest_path, bin_dir = Path(manifest_path), Path(bin_dir)
    if not manifest_path.is_file():
        raise ValueError(f"runtime manifest missing: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid runtime manifest JSON: {exc}") from exc
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported runtime manifest schema: {payload.get('schema_version')!r}")
    source = payload.get("source") or {}
    if source.get("repo") != expected_repo:
        raise ValueError(f"runtime source repo mismatch: expected={expected_repo} actual={source.get('repo')}")
    actual_commit = str(source.get("commit") or "").lower()
    if actual_commit != expected_commit.lower():
        raise ValueError(f"runtime source commit mismatch: expected={expected_commit} actual={actual_commit}")
    arches = _arches((payload.get("build") or {}).get("cuda_architectures") or [])
    if str(required_cuda_arch) not in arches:
        raise ValueError(f"runtime CUDA architecture mismatch: required={required_cuda_arch} actual={arches}")
    binary_meta = payload.get("binaries") or {}
    for name in REQUIRED_BINARIES:
        path = bin_dir / name
        meta = binary_meta.get(name) or {}
        if not path.is_file():
            raise ValueError(f"required runtime binary missing: {path}")
        size = path.stat().st_size
        if meta.get("size_bytes") != size:
            raise ValueError(f"runtime binary size mismatch for {name}: expected={meta.get('size_bytes')} actual={size}")
        digest = _sha256(path)
        if str(meta.get("sha256") or "").lower() != digest:
            raise ValueError(f"runtime binary SHA256 mismatch for {name}: expected={meta.get('sha256')} actual={digest}")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--bin-dir", type=Path, required=True)
    create.add_argument("--repo", required=True)
    create.add_argument("--commit", required=True)
    create.add_argument("--cuda-architectures", required=True)
    create.add_argument("--cuda-version", default="")
    create.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--bin-dir", type=Path, required=True)
    verify.add_argument("--expected-repo", required=True)
    verify.add_argument("--expected-commit", required=True)
    verify.add_argument("--required-cuda-arch", required=True)
    args = ap.parse_args()
    try:
        if args.command == "create":
            payload = create_manifest(args.bin_dir, args.repo, args.commit, args.cuda_architectures, args.cuda_version)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        else:
            payload = verify_manifest(args.manifest, args.bin_dir, args.expected_repo, args.expected_commit, args.required_cuda_arch)
        print(json.dumps(payload, indent=2))
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
