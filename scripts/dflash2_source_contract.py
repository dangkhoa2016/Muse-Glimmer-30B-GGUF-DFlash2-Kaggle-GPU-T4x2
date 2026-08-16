#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES = {
    "src/llama-arch.h": (
        "LLM_KV_DFLASH_BLOCK_SIZE",
        "LLM_KV_DFLASH_CONV_KERNEL_SIZE",
        "LLM_KV_DFLASH_CONV_GROUP_SIZE",
        "LLM_KV_DFLASH_SELECTOR_RANK",
        "LLM_KV_DFLASH_SELECTOR_TOP_K",
        "LLM_TENSOR_DFLASH_SELECTOR_PREV",
        "LLM_TENSOR_DFLASH_SELECTOR_NEXT",
        "LLM_TENSOR_DFLASH_SELECTOR_HIDDEN",
    ),
    "src/llama-arch.cpp": (
        "blk.%d.attn_conv_base",
        "blk.%d.attn_conv_proj",
        "blk.%d.ffn_conv_base",
        "blk.%d.ffn_conv_proj",
        "selector_predecessor",
        "selector_successor",
        "selector_hidden",
    ),
    "src/llama-model.h": (
        "dflash_attn_conv_base",
        "dflash_attn_conv_proj",
        "dflash_ffn_conv_base",
        "dflash_ffn_conv_proj",
        "dflash_selector_hidden",
    ),
    "src/models/dflash.cpp": (
        "LLM_TENSOR_DFLASH_ATTN_CONV_BASE",
        "LLM_TENSOR_DFLASH_ATTN_CONV_PROJ",
        "LLM_TENSOR_DFLASH_FFN_CONV_BASE",
        "LLM_TENSOR_DFLASH_FFN_CONV_PROJ",
        "LLM_TENSOR_DFLASH_SELECTOR_PREV",
        "LLM_TENSOR_DFLASH_SELECTOR_NEXT",
        "LLM_TENSOR_DFLASH_SELECTOR_HIDDEN",
        "build_dflash2_conv",
    ),
}


def validate_source(
    source: Path, expected_commit: str, resolved_commit: str
) -> list[str]:
    errors = []
    if resolved_commit != expected_commit:
        errors.append(
            f"commit mismatch: expected={expected_commit} resolved={resolved_commit}"
        )
    for rel, tokens in REQUIRED_FILES.items():
        path = source / rel
        if not path.is_file():
            errors.append(f"missing source file: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        errors.extend(f"{rel}: missing {token}" for token in tokens if token not in text)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the DFlash2 source contract")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()

    resolved = subprocess.run(
        ["git", "-C", str(args.source), "rev-parse", "HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    errors = validate_source(args.source, args.expected_commit, resolved)
    if errors:
        for error in errors:
            print(f"ERROR: DFlash2 source contract: {error}", file=sys.stderr)
        if any(error.startswith("commit mismatch:") for error in errors):
            return 3
        return 4

    print(f"DFlash2 source contract: OK commit={resolved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
