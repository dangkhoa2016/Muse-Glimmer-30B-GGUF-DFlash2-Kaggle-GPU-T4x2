#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$PROJECT_ROOT/scripts/common.sh"

MODEL_PATH="$MODELS_DIR/$MODEL_FILE"
CONFIG_EXPECTED_SIZE="$(model_expected_size)"
CONFIG_EXPECTED_SHA="$(model_expected_sha256)"
MODEL_STATE="$RUNTIME_STATE_DIR/model.env"
mkdir -p "$MODELS_DIR" "$RUNTIME_STATE_DIR"

verify_file() {
  local path="$1" expected_size="${2:-}" expected_sha="${3:-}" size actual
  [[ -f "$path" ]] || return 1
  size="$(stat -Lc '%s' "$path" 2>/dev/null || stat -Lf '%z' "$path")"
  if [[ -n "$expected_size" && "$size" != "$expected_size" ]]; then
    echo "VERIFY: size mismatch for $path: got=$size expected=$expected_size" >&2
    return 1
  fi
  if [[ "${VERIFY_MODEL_SHA256:-1}" == 1 && -n "$expected_sha" ]]; then
    actual="$(sha256sum "$path" | awk '{print $1}')"
    if [[ "$actual" != "$expected_sha" ]]; then
      echo "VERIFY: sha256 mismatch for $path: got=$actual expected=$expected_sha" >&2
      return 1
    fi
  fi
  return 0
}

write_model_state() {
  local path="$1" source="$2" dataset_root="${3:-}" expected_sha="${4:-}" metadata_source="${5:-}" selection="${6:-exact}" verification_seconds="${7:-0}" digest size
  size="$(stat -Lc '%s' "$path" 2>/dev/null || stat -Lf '%z' "$path")"
  if [[ -n "$expected_sha" ]]; then digest="$expected_sha"; else digest="$(sha256sum "$path" | awk '{print $1}')"; fi
  {
    printf 'MODEL_RESOLVED_PATH=%q\n' "$path"
    printf 'MODEL_RESOLVED_FILE=%q\n' "$(basename "$path")"
    printf 'MODEL_RUNTIME_SOURCE=%q\n' "$source"
    printf 'MODEL_RUNTIME_DATASET_ROOT=%q\n' "$dataset_root"
    printf 'MODEL_RESOLVED_SIZE_BYTES=%q\n' "$size"
    printf 'MODEL_RESOLVED_SHA256=%q\n' "$digest"
    printf 'MODEL_METADATA_SOURCE=%q\n' "$metadata_source"
    printf 'MODEL_SELECTION=%q\n' "$selection"
    printf 'MODEL_VERIFICATION_SECONDS=%q\n' "$verification_seconds"
  } > "$MODEL_STATE"
  printf '%s  %s\n' "$digest" "$path" > "$RUNTIME_STATE_DIR/model.sha256"
}

find_kaggle_model_json() {
  python3 "$PROJECT_ROOT/scripts/kaggle_runtime.py" \
    --input-root "$KAGGLE_INPUT_ROOT" \
    --dataset-slug "${KAGGLE_MODEL_DATASET:-$KAGGLE_RUNTIME_DATASET}" \
    --model-file "$MODEL_FILE" \
    --model-aliases "${KAGGLE_MODEL_ALIASES:-}"
}

case "${MODEL_SOURCE_MODE:-auto}" in auto|kaggle|local|hf) ;; *) echo "ERROR: MODEL_SOURCE_MODE must be auto|kaggle|local|hf" >&2; exit 2;; esac
case "${MODEL_SELECTION_POLICY:-verified_fallback}" in verified_fallback|exact) ;; *) echo "ERROR: MODEL_SELECTION_POLICY must be verified_fallback|exact" >&2; exit 2;; esac

if [[ "${FORCE_MODEL_DOWNLOAD:-0}" != 1 && ( "$MODEL_SOURCE_MODE" == auto || "$MODEL_SOURCE_MODE" == kaggle ) ]]; then
  discovery="$(find_kaggle_model_json)"
  mapfile -t found < <(python3 -c '
import json,sys
x=json.load(sys.stdin)
for k in ("model_path","dataset_root","model_selection","model_size_bytes","model_sha256","model_sha256_source"):
    v=x.get(k)
    print("" if v is None else v)
' <<< "$discovery")
  kaggle_model="${found[0]:-}"; kaggle_root="${found[1]:-}"; selection="${found[2]:-}"
  discovered_size="${found[3]:-}"; discovered_sha="${found[4]:-}"; sha_source="${found[5]:-}"
  if [[ -n "$kaggle_model" ]]; then
    echo "Kaggle input model candidate: $kaggle_model (selection=${selection:-unknown})"
    if [[ "${MODEL_SELECTION_POLICY:-verified_fallback}" == exact && "${selection:-}" != exact ]]; then
      echo "Kaggle candidate rejected: MODEL_SELECTION_POLICY=exact requires an exact filename match for '$MODEL_FILE'; discovered selection=${selection:-unknown}." >&2
      if [[ "$MODEL_SOURCE_MODE" == kaggle ]]; then exit 4; fi
      kaggle_model=""
    fi
    expected_size="$CONFIG_EXPECTED_SIZE"; expected_sha="$CONFIG_EXPECTED_SHA"; metadata_source=config
    if [[ "$selection" != exact ]]; then
      expected_size="$discovered_size"; expected_sha="$discovered_sha"; metadata_source="${sha_source:-dataset_discovery}"
      if [[ "${VERIFY_MODEL_SHA256:-1}" == 1 && -z "$expected_sha" ]]; then
        echo "Kaggle fallback model '$kaggle_model' is not the configured artifact and has no trusted SHA256SUMS entry; refusing silent quant/artifact substitution." >&2
        [[ "$MODEL_SOURCE_MODE" == kaggle ]] && exit 4
        kaggle_model=""
      fi
    elif [[ -n "$discovered_sha" && -n "$CONFIG_EXPECTED_SHA" && "$discovered_sha" != "$CONFIG_EXPECTED_SHA" ]]; then
      echo "Kaggle exact-name model SHA256SUMS disagrees with configured hash; refusing candidate." >&2
      [[ "$MODEL_SOURCE_MODE" == kaggle ]] && exit 4
      kaggle_model=""
    fi
    verify_started="$(monotonic_now)"
    if [[ -n "$kaggle_model" ]] && verify_file "$kaggle_model" "$expected_size" "$expected_sha"; then
      verification_seconds="$(elapsed_since "$verify_started")"
      echo 'Kaggle input model verification: OK; using read-only input directly (no copy).'
      write_model_state "$kaggle_model" kaggle_input "$kaggle_root" "$expected_sha" "$metadata_source" "${selection:-exact}" "$verification_seconds"
      ls -lh "$kaggle_model"
      exit 0
    elif [[ -n "$kaggle_model" ]]; then
      echo 'Kaggle input model failed integrity verification.' >&2
      [[ "$MODEL_SOURCE_MODE" == kaggle ]] && exit 4
    fi
  elif [[ "$MODEL_SOURCE_MODE" == kaggle ]]; then
    echo "ERROR: model not found in attached Kaggle model '${KAGGLE_MODEL_DATASET:-$KAGGLE_RUNTIME_DATASET}' under $KAGGLE_INPUT_ROOT" >&2
    exit 3
  fi
fi

recover_incomplete() {
  [[ "${RECOVER_HF_INCOMPLETE:-1}" == 1 ]] || return 1
  [[ -n "$CONFIG_EXPECTED_SIZE" && -n "$CONFIG_EXPECTED_SHA" ]] || return 1
  local candidate size digest
  while IFS= read -r -d '' candidate; do
    size="$(stat -Lc '%s' "$candidate" 2>/dev/null || stat -Lf '%z' "$candidate" 2>/dev/null || echo 0)"
    [[ "$size" == "$CONFIG_EXPECTED_SIZE" ]] || continue
    echo "Recovery candidate has expected size: $candidate"
    digest="$(sha256sum "$candidate" | awk '{print $1}')"
    if [[ "$digest" == "$CONFIG_EXPECTED_SHA" ]]; then mv -f "$candidate" "$MODEL_PATH"; return 0; fi
  done < <(find "$MODELS_DIR" -type f -name '*.incomplete' -print0 2>/dev/null)
  return 1
}

if [[ "${FORCE_MODEL_DOWNLOAD:-0}" == 1 && -f "$MODEL_PATH" ]]; then rm -f "$MODEL_PATH" "$MODELS_DIR/${MODEL_FILE}.sha256"; fi
if [[ "$MODEL_SOURCE_MODE" != hf && -f "$MODEL_PATH" ]]; then
  echo "Existing local model: $MODEL_PATH"
  verify_started="$(monotonic_now)"
  if verify_file "$MODEL_PATH" "$CONFIG_EXPECTED_SIZE" "$CONFIG_EXPECTED_SHA"; then
    verification_seconds="$(elapsed_since "$verify_started")"
    echo 'Existing local model verification: OK'
    write_model_state "$MODEL_PATH" local_cache "" "$CONFIG_EXPECTED_SHA" config exact "$verification_seconds"
    exit 0
  fi
  echo 'Existing local model verification failed; removing invalid file.' >&2
  rm -f "$MODEL_PATH"
fi
[[ "$MODEL_SOURCE_MODE" == local ]] && { echo "ERROR: local model required but missing: $MODEL_PATH" >&2; exit 3; }

HF="$(hf_bin)"
[[ -n "$HF" ]] || { echo 'ERROR: hf CLI not found for Hugging Face fallback; run setup.sh' >&2; exit 2; }
echo "Downloading $MODEL_REPO / $MODEL_FILE"
[[ -n "${HF_TOKEN:-}" ]] && echo 'HF_TOKEN: set' || echo 'HF_TOKEN: not set'
set +e
"$HF" download "$MODEL_REPO" "$MODEL_FILE" --local-dir "$MODELS_DIR"
rc=$?
set -e
if (( rc != 0 )); then
  echo "hf download exit=$rc; attempting verified incomplete-file recovery..." >&2
  recover_incomplete || { echo 'ERROR: download failed and no verified recoverable incomplete file was found.' >&2; exit "$rc"; }
fi
[[ -f "$MODEL_PATH" ]] || { echo 'ERROR: model missing after download/recovery' >&2; exit 3; }
verify_started="$(monotonic_now)"
verify_file "$MODEL_PATH" "$CONFIG_EXPECTED_SIZE" "$CONFIG_EXPECTED_SHA" || { echo 'ERROR: final model verification failed' >&2; exit 4; }
verification_seconds="$(elapsed_since "$verify_started")"
write_model_state "$MODEL_PATH" huggingface_download "" "$CONFIG_EXPECTED_SHA" config exact "$verification_seconds"
ls -lh "$MODEL_PATH"
if [[ -n "$CONFIG_EXPECTED_SHA" ]]; then printf '%s  %s\n' "$CONFIG_EXPECTED_SHA" "$MODEL_PATH" | tee "$MODELS_DIR/${MODEL_FILE}.sha256"; else sha256sum "$MODEL_PATH" | tee "$MODELS_DIR/${MODEL_FILE}.sha256"; fi
