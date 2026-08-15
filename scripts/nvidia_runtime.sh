#!/usr/bin/env bash
# Sourceable NVIDIA management-runtime discovery for Kaggle GPU shells.

_nvidia_colon_has_dir() {
  local list="${1:-}" needle="${2:-}"
  [[ -n "$needle" ]] || return 1
  case ":$list:" in *":$needle:"*) return 0 ;; *) return 1 ;; esac
}

_nvidia_prepend_unique() {
  local var="$1" dir="$2" current
  [[ -n "$dir" ]] || return 0
  current="${!var:-}"
  if ! _nvidia_colon_has_dir "$current" "$dir"; then
    if [[ -n "$current" ]]; then
      printf -v "$var" '%s:%s' "$dir" "$current"
    else
      printf -v "$var" '%s' "$dir"
    fi
    export "$var"
    return 10
  fi
  return 0
}

_nvidia_realpath() {
  local path="$1"
  if command -v realpath >/dev/null 2>&1; then realpath "$path" 2>/dev/null || printf '%s\n' "$path"
  elif command -v readlink >/dev/null 2>&1; then readlink -f "$path" 2>/dev/null || printf '%s\n' "$path"
  else printf '%s\n' "$path"
  fi
}

_nvidia_find_ml_library() {
  local dir entry
  local -a dirs=() configured=()
  IFS=':' read -r -a dirs <<< "${LD_LIBRARY_PATH:-}"
  IFS=':' read -r -a configured <<< "${NVIDIA_DRIVER_LIB_SEARCH_DIRS:-/usr/local/nvidia/lib64:/usr/local/nvidia/lib:/usr/lib/x86_64-linux-gnu:/usr/lib64:/lib/x86_64-linux-gnu}"
  dirs+=("${configured[@]}")
  for dir in "${dirs[@]}"; do
    [[ -n "$dir" && -d "$dir" ]] || continue
    for entry in "$dir/libnvidia-ml.so.1" "$dir/libnvidia-ml.so"; do
      if [[ -e "$entry" ]]; then printf '%s\n' "$entry"; return 0; fi
    done
  done
  if command -v ldconfig >/dev/null 2>&1; then
    entry="$(ldconfig -p 2>/dev/null | awk '/libnvidia-ml\.so(\.1)? / {print $NF; exit}' || true)"
    [[ -n "$entry" && -e "$entry" ]] && { printf '%s\n' "$entry"; return 0; }
  fi
  return 1
}

_nvidia_select_smi() {
  local candidate found=""
  local -a candidates=()
  if [[ -n "${NVIDIA_SMI:-}" ]]; then
    [[ -x "$NVIDIA_SMI" ]] || { echo "ERROR: explicit NVIDIA_SMI is not executable: $NVIDIA_SMI" >&2; return 1; }
    printf '%s\n' "$NVIDIA_SMI"
    return 0
  fi
  found="$(command -v nvidia-smi 2>/dev/null || true)"
  if [[ -n "$found" && -x "$found" ]]; then printf '%s\n' "$found"; return 0; fi
  IFS=':' read -r -a candidates <<< "${NVIDIA_SMI_SEARCH_PATHS:-/opt/bin/nvidia-smi:/usr/bin/nvidia-smi:/usr/local/bin/nvidia-smi:/usr/local/nvidia/bin/nvidia-smi}"
  for candidate in "${candidates[@]}"; do
    [[ -x "$candidate" ]] && { printf '%s\n' "$candidate"; return 0; }
  done
  echo 'ERROR: nvidia-smi is unavailable. Checked PATH and configured NVIDIA_SMI_SEARCH_PATHS.' >&2
  return 1
}

_nvidia_probe_smi() {
  local smi="$1"
  "$smi" --query-gpu=index --format=csv,noheader,nounits >/dev/null 2>&1
}

resolve_nvidia_runtime() {
  local selected ml="" probe_before=0 path_added=0 ld_added=0
  selected="$(_nvidia_select_smi)" || return 1

  NVIDIA_SMI_PATH="$selected"
  NVIDIA_SMI_REALPATH="$(_nvidia_realpath "$selected")"
  NVIDIA_SMI_BIN_DIR="$(dirname "$selected")"

  if _nvidia_probe_smi "$NVIDIA_SMI_PATH"; then probe_before=1; fi

  ml="$(_nvidia_find_ml_library 2>/dev/null || true)"
  NVIDIA_ML_LIBRARY="$ml"
  NVIDIA_DRIVER_LIB_DIR=""
  [[ -n "$ml" ]] && NVIDIA_DRIVER_LIB_DIR="$(dirname "$ml")"

  local path_rc=0
  if _nvidia_prepend_unique PATH "$NVIDIA_SMI_BIN_DIR"; then path_rc=0; else path_rc=$?; fi
  (( path_rc == 10 )) && path_added=1

  if (( ! probe_before )); then
    if [[ -z "$NVIDIA_DRIVER_LIB_DIR" ]]; then
      echo "ERROR: $NVIDIA_SMI_PATH cannot query the driver and libnvidia-ml.so could not be located." >&2
      return 1
    fi
    local ld_rc=0
    if _nvidia_prepend_unique LD_LIBRARY_PATH "$NVIDIA_DRIVER_LIB_DIR"; then ld_rc=0; else ld_rc=$?; fi
    (( ld_rc == 10 )) && ld_added=1
    if ! _nvidia_probe_smi "$NVIDIA_SMI_PATH"; then
      echo "ERROR: nvidia-smi was found at $NVIDIA_SMI_PATH but still cannot query the NVIDIA driver after runtime-library discovery." >&2
      return 1
    fi
  fi

  NVIDIA_RUNTIME_LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
  NVIDIA_RUNTIME_PATH_INJECTED="$path_added"
  NVIDIA_RUNTIME_LD_LIBRARY_INJECTED="$ld_added"
  export NVIDIA_SMI_PATH NVIDIA_SMI_REALPATH NVIDIA_SMI_BIN_DIR NVIDIA_ML_LIBRARY NVIDIA_DRIVER_LIB_DIR \
    NVIDIA_RUNTIME_LD_LIBRARY_PATH NVIDIA_RUNTIME_PATH_INJECTED NVIDIA_RUNTIME_LD_LIBRARY_INJECTED PATH LD_LIBRARY_PATH
}

apply_nvidia_runtime_env() {
  local rc=0
  if [[ -n "${NVIDIA_SMI_BIN_DIR:-}" ]]; then
    if _nvidia_prepend_unique PATH "$NVIDIA_SMI_BIN_DIR"; then rc=0; else rc=$?; fi
    [[ $rc -eq 0 || $rc -eq 10 ]] || return "$rc"
  fi
  if [[ -n "${NVIDIA_DRIVER_LIB_DIR:-}" ]]; then
    if _nvidia_prepend_unique LD_LIBRARY_PATH "$NVIDIA_DRIVER_LIB_DIR"; then rc=0; else rc=$?; fi
    [[ $rc -eq 0 || $rc -eq 10 ]] || return "$rc"
  fi
  export PATH LD_LIBRARY_PATH
}

write_nvidia_runtime_state() {
  local target="${1:?usage: write_nvidia_runtime_state PATH}"
  mkdir -p "$(dirname "$target")"
  {
    printf 'NVIDIA_SMI_PATH=%q\n' "${NVIDIA_SMI_PATH:-}"
    printf 'NVIDIA_SMI_REALPATH=%q\n' "${NVIDIA_SMI_REALPATH:-}"
    printf 'NVIDIA_SMI_BIN_DIR=%q\n' "${NVIDIA_SMI_BIN_DIR:-}"
    printf 'NVIDIA_ML_LIBRARY=%q\n' "${NVIDIA_ML_LIBRARY:-}"
    printf 'NVIDIA_DRIVER_LIB_DIR=%q\n' "${NVIDIA_DRIVER_LIB_DIR:-}"
    printf 'NVIDIA_RUNTIME_LD_LIBRARY_PATH=%q\n' "${NVIDIA_RUNTIME_LD_LIBRARY_PATH:-}"
    printf 'NVIDIA_RUNTIME_PATH_INJECTED=%q\n' "${NVIDIA_RUNTIME_PATH_INJECTED:-0}"
    printf 'NVIDIA_RUNTIME_LD_LIBRARY_INJECTED=%q\n' "${NVIDIA_RUNTIME_LD_LIBRARY_INJECTED:-0}"
  } > "$target"
}
