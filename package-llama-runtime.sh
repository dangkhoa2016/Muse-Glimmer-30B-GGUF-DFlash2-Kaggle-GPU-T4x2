#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/scripts/common.sh"
STATE="$RUNTIME_STATE_DIR/llama.env"
[[ -f "$STATE" ]] || { echo "ERROR: runtime state missing: $STATE; run setup first." >&2; exit 2; }
# shellcheck disable=SC1090
source "$STATE"
BIN_DIR="${LLAMA_RESOLVED_BIN_DIR:?LLAMA_RESOLVED_BIN_DIR missing from runtime state}"
COMMIT="${LLAMA_SOURCE_SNAPSHOT:-${LLAMA_CPP_EXPECTED_COMMIT:-}}"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR: exact 40-char source commit unavailable in runtime state." >&2; exit 3; }
OUT="${1:-/kaggle/working/muse-glimmer-30b-dflash2-llama-runtime}"
LIB_DIR=""
if [[ -n "${LLAMA_BUILD_DIR:-}" && -d "$LLAMA_BUILD_DIR/lib" ]]; then LIB_DIR="$LLAMA_BUILD_DIR/lib"; fi
args=(--bin-dir "$BIN_DIR" --output-dir "$OUT" --repo "$LLAMA_CPP_REPO" --commit "$COMMIT" --cuda-architectures "$CUDA_ARCHITECTURES" --cuda-version "${LLAMA_BUILD_CUDA_VERSION:-${CUDA_TOOLKIT_VERSION:-}}")
[[ -n "$LIB_DIR" ]] && args+=(--lib-dir "$LIB_DIR")
python3 "$ROOT/scripts/package_llama_runtime.py" "${args[@]}"
echo "Runtime package ready: $OUT"
echo "Attach/publish it with Kaggle dataset slug: $KAGGLE_RUNTIME_DATASET"
