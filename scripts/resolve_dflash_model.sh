#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
root="${DFLASH_KAGGLE_INPUT_ROOT:-/kaggle/input}"
model_slug="${DFLASH_KAGGLE_MODEL_DATASET:-}"
explicit="${DFLASH_MODEL_PATH:-}"
filename="${DFLASH_MODEL_FILE:-Muse-Glimmer-30B-DFlash2-Q4_K_M.gguf}"
expected_size="${DFLASH_MODEL_SIZE_BYTES:-}"
expected_sha="${DFLASH_MODEL_SHA256:-}"
verify_sha="${VERIFY_DFLASH_SHA256:-1}"

validate() {
  local path="$1" actual_size actual_sha
  [[ -f "$path" ]] || { echo "ERROR: DFlash2 model does not exist: $path" >&2; return 2; }
  actual_size="$(stat -Lc '%s' "$path")"
  if [[ -n "$expected_size" && "$actual_size" != "$expected_size" ]]; then
    echo "ERROR: DFlash2 size mismatch for $path: expected=$expected_size actual=$actual_size" >&2
    return 3
  fi
  case "$verify_sha" in 0|1) ;; *) echo "ERROR: VERIFY_DFLASH_SHA256 must be 0 or 1" >&2; return 2;; esac
  if [[ "$verify_sha" == 1 && -n "$expected_sha" ]]; then
    actual_sha="$(sha256sum "$path" | awk '{print $1}')"
    if [[ "$actual_sha" != "$expected_sha" ]]; then
      echo "ERROR: DFlash2 SHA256 mismatch for $path: expected=$expected_sha actual=$actual_sha" >&2
      return 4
    fi
  fi
  python3 - "$path" <<'PY'
import os,sys
print(os.path.abspath(sys.argv[1]))
PY
}

# Explicit paths remain useful for diagnostics, and are still identity-validated.
if [[ -n "$explicit" ]]; then
  validate "$explicit"
  exit $?
fi

[[ -d "$root" ]] || { echo "ERROR: DFlash2 Kaggle input root does not exist: $root" >&2; exit 2; }

# Discovery is scoped to the specific attached Kaggle model rather than scanning
# every input for a coincidentally matching filename.
if [[ -n "$model_slug" ]]; then
  discovery="$(python3 "$PROJECT_ROOT/scripts/kaggle_runtime.py" \
    --input-root "$root" --dataset-slug "$model_slug" --model-file "$filename" --model-aliases '')"
  mapfile -t found < <(python3 -c '
import json,sys
x=json.load(sys.stdin)
print(x.get("dataset_root") or "")
print(x.get("model_path") or "")
print(x.get("model_selection") or "")
print(len(x.get("dataset_candidates") or []))
for p in x.get("dataset_candidates") or []:
    print(p)
' <<< "$discovery")
  dataset_root="${found[0]:-}"
  candidate="${found[1]:-}"
  selection="${found[2]:-}"
  candidate_count="${found[3]:-0}"
  if [[ -z "$dataset_root" ]]; then
    if (( candidate_count > 1 )); then
      echo "ERROR: ambiguous DFlash2 Kaggle model root '$model_slug' under $root; attach only one matching model root or set DFLASH_MODEL_PATH explicitly." >&2
      printf '  %s\n' "${found[@]:4}" >&2
    else
      echo "ERROR: attached DFlash2 Kaggle model '$model_slug' not found under $root." >&2
    fi
    exit 2
  fi
  [[ "$selection" == exact && -n "$candidate" ]] || {
    echo "ERROR: exact DFlash2 file '$filename' not found inside attached Kaggle model root $dataset_root." >&2
    exit 2
  }
  validate "$candidate"
  exit $?
fi

# Compatibility fallback for an explicitly unscoped configuration.
mapfile -d '' -t candidates < <(find "$root" -type f -name "$filename" -print0 2>/dev/null | sort -z)
case "${#candidates[@]}" in
  0) echo "ERROR: no exact DFlash2 candidate named '$filename' found under $root; set DFLASH_MODEL_PATH explicitly." >&2; exit 2 ;;
  1) validate "${candidates[0]}" ;;
  *)
    echo "ERROR: multiple exact DFlash2 candidates named '$filename' found under $root; set DFLASH_MODEL_PATH explicitly." >&2
    printf '  %s\n' "${candidates[@]}" >&2
    exit 2
    ;;
esac
