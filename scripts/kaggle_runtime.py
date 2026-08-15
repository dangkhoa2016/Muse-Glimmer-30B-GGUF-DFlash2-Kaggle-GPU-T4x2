#!/usr/bin/env python3
"""Discover Muse-Glimmer model/runtime/source assets in attached Kaggle datasets."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

REQUIRED_LLAMA_BINARIES = ("llama-server", "llama-cli", "llama-bench")
SNAPSHOT_RE = re.compile(r"(?:llama(?:\.cpp)?[-_])([0-9a-f]{7,40})(?:$|[^0-9a-f])", re.I)
SHA256_RE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$")


def _shortest(paths: Iterable[Path]) -> Path | None:
    paths = list(paths)
    if not paths:
        return None
    return sorted(paths, key=lambda p: (len(p.parts), p.as_posix()))[0]


def _dataset_candidates(input_root: Path, dataset_slug: str) -> list[Path]:
    candidates: list[Path] = []
    exact = input_root / dataset_slug
    if exact.is_dir():
        candidates.append(exact)

    datasets_dir = input_root / "datasets"
    if datasets_dir.is_dir():
        for owner_dir in sorted(p for p in datasets_dir.iterdir() if p.is_dir()):
            p = owner_dir / dataset_slug
            if p.is_dir():
                candidates.append(p)

    if input_root.is_dir():
        for p in input_root.rglob(dataset_slug):
            if p.is_dir() and p not in candidates:
                candidates.append(p)
    return sorted(candidates, key=lambda p: (len(p.parts), p.as_posix()))


def _select_dataset_root(input_root: Path, dataset_slug: str) -> tuple[Path | None, list[Path]]:
    candidates = _dataset_candidates(input_root, dataset_slug)
    if not candidates:
        return None, []
    exact = input_root / dataset_slug
    if exact in candidates:
        return exact, candidates
    owner_candidates = [p for p in candidates if p.parent.parent == input_root / "datasets"]
    if len(owner_candidates) == 1:
        return owner_candidates[0], candidates
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


def _parse_sha256sums(dataset_root: Path) -> tuple[dict[str, str], Path | None]:
    files = sorted(
        [p for p in dataset_root.rglob("SHA256SUMS") if p.is_file()],
        key=lambda p: (len(p.parts), p.as_posix()),
    )
    if not files:
        return {}, None
    path = files[0]
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = SHA256_RE.match(line)
        if not m:
            continue
        rel = m.group(2).strip()
        if rel.startswith("./"):
            rel = rel[2:]
        entries[rel] = m.group(1).lower()
    return entries, path


def _sha_for_model(model: Path, dataset_root: Path, entries: dict[str, str]) -> str | None:
    rel = model.relative_to(dataset_root).as_posix()
    if rel in entries:
        return entries[rel]
    if model.name in entries:
        return entries[model.name]
    basename_matches = [digest for key, digest in entries.items() if Path(key).name == model.name]
    if len(set(basename_matches)) == 1 and basename_matches:
        return basename_matches[0]
    return None


def _select_model(dataset_root: Path, model_file: str, aliases: list[str]) -> tuple[Path | None, str | None]:
    exact = _shortest(p for p in dataset_root.rglob(model_file) if p.is_file())
    if exact is not None:
        return exact, "exact"
    for alias in aliases:
        alias = alias.strip()
        if not alias:
            continue
        found = _shortest(p for p in dataset_root.rglob(alias) if p.is_file())
        if found is not None:
            return found, "alias"
    ggufs = sorted(
        [p for p in dataset_root.rglob("*.gguf") if p.is_file()],
        key=lambda p: (len(p.parts), p.as_posix()),
    )
    if len(ggufs) == 1:
        return ggufs[0], "single_gguf"
    return None, None


def _source_snapshot(source_dir: Path, dataset_root: Path) -> str | None:
    current = source_dir
    while True:
        m = SNAPSHOT_RE.search(current.name)
        if m:
            return m.group(1).lower()
        if current == dataset_root or dataset_root not in current.parents:
            break
        current = current.parent
    return None


def _discover_llama_source(dataset_root: Path) -> tuple[Path | None, str | None]:
    candidates: list[Path] = []
    for arch in dataset_root.rglob("llama-arch.cpp"):
        if not arch.is_file() or arch.parent.name != "src":
            continue
        source = arch.parent.parent
        if not (source / "CMakeLists.txt").is_file():
            continue
        try:
            text = arch.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "LLM_ARCH_MUSE_GLIMMER" not in text:
            continue
        candidates.append(source)
    source = _shortest(candidates)
    return (source, _source_snapshot(source, dataset_root) if source else None)


def discover_runtime(
    input_root: Path | str,
    dataset_slug: str,
    model_file: str,
    model_aliases: list[str] | None = None,
) -> dict[str, Any]:
    input_root = Path(input_root)
    dataset_root, dataset_candidates = _select_dataset_root(input_root, dataset_slug)
    result: dict[str, Any] = {
        "input_root": str(input_root),
        "dataset_slug": dataset_slug,
        "dataset_root": str(dataset_root) if dataset_root else None,
        "dataset_candidates": [str(p) for p in dataset_candidates],
        "dataset_found": dataset_root is not None,
        "model_path": None,
        "model_found": False,
        "model_selection": None,
        "model_size_bytes": None,
        "model_sha256": None,
        "model_sha256_source": None,
        "sha256sums_path": None,
        "llama_bin_dir": None,
        "llama_runtime_found": False,
        "llama_server": None,
        "llama_cli": None,
        "llama_bench": None,
        "llama_source_dir": None,
        "llama_source_found": False,
        "llama_source_snapshot": None,
    }
    if dataset_root is None:
        return result

    aliases = model_aliases or []
    model, selection = _select_model(dataset_root, model_file, aliases)
    entries, sums_path = _parse_sha256sums(dataset_root)
    if sums_path is not None:
        result["sha256sums_path"] = str(sums_path)
    if model is not None:
        result["model_path"] = str(model)
        result["model_found"] = True
        result["model_selection"] = selection
        result["model_size_bytes"] = model.stat().st_size
        digest = _sha_for_model(model, dataset_root, entries)
        if digest:
            result["model_sha256"] = digest
            result["model_sha256_source"] = "SHA256SUMS"

    bin_dirs: list[Path] = []
    for server in dataset_root.rglob("llama-server"):
        if not server.is_file():
            continue
        parent = server.parent
        if all((parent / name).is_file() for name in REQUIRED_LLAMA_BINARIES):
            bin_dirs.append(parent)
    bin_dir = _shortest(bin_dirs)
    if bin_dir is not None:
        result["llama_bin_dir"] = str(bin_dir)
        result["llama_runtime_found"] = True
        result["llama_server"] = str(bin_dir / "llama-server")
        result["llama_cli"] = str(bin_dir / "llama-cli")
        result["llama_bench"] = str(bin_dir / "llama-bench")

    source_dir, snapshot = _discover_llama_source(dataset_root)
    if source_dir is not None:
        result["llama_source_dir"] = str(source_dir)
        result["llama_source_found"] = True
        result["llama_source_snapshot"] = snapshot
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default="/kaggle/input")
    ap.add_argument("--dataset-slug", default="muse-glimmer-30b-gguf-runtime")
    ap.add_argument("--model-file", required=True)
    ap.add_argument("--model-aliases", default="")
    ap.add_argument("--output")
    args = ap.parse_args()
    aliases = [x.strip() for x in args.model_aliases.split(",") if x.strip()]
    result = discover_runtime(args.input_root, args.dataset_slug, args.model_file, aliases)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
