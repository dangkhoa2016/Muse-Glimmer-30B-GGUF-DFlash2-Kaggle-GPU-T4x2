#!/usr/bin/env bash
# Sourceable CUDA toolkit discovery/preflight for Kaggle T4x2 builds.
# Intentionally does not enable shell options so callers keep their own policy.

_cuda_realpath() {
  local p="$1"
  if command -v realpath >/dev/null 2>&1; then realpath "$p" 2>/dev/null
  else readlink -f "$p" 2>/dev/null
  fi
}

_cuda_find_cudart() {
  local root="$1" candidate
  for candidate in \
    "$root/lib64/libcudart.so" \
    "$root/targets/x86_64-linux/lib/libcudart.so" \
    "$root/lib/libcudart.so"; do
    if [[ -e "$candidate" ]]; then printf '%s\n' "$candidate"; return 0; fi
  done
  return 1
}

_cuda_validate_candidate() {
  local root="$1" nvcc_path="$2" root_real nvcc_real header cudart
  root_real="$(_cuda_realpath "$root")" || {
    echo "CUDA toolkit candidate root does not resolve: $root" >&2
    return 1
  }
  [[ -d "$root_real" ]] || { echo "CUDA toolkit candidate root is not a directory: $root_real" >&2; return 1; }
  nvcc_real="$(_cuda_realpath "$nvcc_path")" || {
    echo "CUDA nvcc does not resolve: $nvcc_path" >&2
    return 1
  }
  [[ -x "$nvcc_real" ]] || { echo "CUDA nvcc is not executable: $nvcc_real" >&2; return 1; }
  header="$root_real/include/cuda_runtime.h"
  [[ -f "$header" ]] || { echo "CUDA toolkit missing cuda_runtime.h: $header" >&2; return 1; }
  cudart="$(_cuda_find_cudart "$root_real")" || {
    echo "CUDA toolkit missing libcudart.so below: $root_real" >&2
    return 1
  }

  CUDA_TOOLKIT_ROOT_RESOLVED="$root_real"
  CUDA_NVCC_PATH="$nvcc_path"
  CUDA_NVCC_REALPATH="$nvcc_real"
  CUDA_RUNTIME_HEADER="$header"
  CUDA_CUDART_PATH="$cudart"
  return 0
}

resolve_cuda_toolkit() {
  local explicit_root="${CUDAToolkit_ROOT:-}"
  local explicit_nvcc="${CUDACXX:-${CMAKE_CUDA_COMPILER:-}}"
  local nvcc_on_path="" nvcc_real="" derived_root="" candidate="" candidate_nvcc=""
  local -a roots=()

  if [[ -n "$explicit_root" ]]; then
    candidate_nvcc="${explicit_nvcc:-$explicit_root/bin/nvcc}"
    if ! _cuda_validate_candidate "$explicit_root" "$candidate_nvcc"; then
      echo "ERROR: explicit CUDA toolkit override is invalid: CUDAToolkit_ROOT=$explicit_root CUDACXX=${explicit_nvcc:-<unset>}" >&2
      return 1
    fi
  elif [[ -n "$explicit_nvcc" ]]; then
    nvcc_real="$(_cuda_realpath "$explicit_nvcc")" || {
      echo "ERROR: explicit CUDA compiler does not resolve: $explicit_nvcc" >&2
      return 1
    }
    derived_root="$(dirname "$(dirname "$nvcc_real")")"
    if ! _cuda_validate_candidate "$derived_root" "$explicit_nvcc"; then
      echo "ERROR: CUDA toolkit derived from explicit compiler is invalid: $derived_root" >&2
      return 1
    fi
  else
    nvcc_on_path="$(command -v nvcc 2>/dev/null || true)"
    if [[ -n "$nvcc_on_path" ]]; then
      nvcc_real="$(_cuda_realpath "$nvcc_on_path" || true)"
      if [[ -n "$nvcc_real" ]]; then roots+=("$(dirname "$(dirname "$nvcc_real")")"); fi
    fi
    [[ -e /usr/local/cuda ]] && roots+=(/usr/local/cuda)
    while IFS= read -r candidate; do roots+=("$candidate"); done < <(find /usr/local -maxdepth 1 -mindepth 1 -type d -name 'cuda-*' -print 2>/dev/null | sort -V -r)

    local seen='|' root_real
    for candidate in "${roots[@]}"; do
      root_real="$(_cuda_realpath "$candidate" 2>/dev/null || true)"
      [[ -n "$root_real" ]] || continue
      [[ "$seen" == *"|$root_real|"* ]] && continue
      seen+="$root_real|"
      if [[ -n "$nvcc_on_path" && "$root_real" == "$(dirname "$(dirname "${nvcc_real:-/nonexistent}")")" ]]; then
        candidate_nvcc="$nvcc_on_path"
      else
        candidate_nvcc="$root_real/bin/nvcc"
      fi
      if _cuda_validate_candidate "$root_real" "$candidate_nvcc"; then
        break
      fi
      CUDA_TOOLKIT_ROOT_RESOLVED=''
    done
    if [[ -z "${CUDA_TOOLKIT_ROOT_RESOLVED:-}" ]]; then
      echo "ERROR: CUDA toolkit preflight failed; no valid toolkit with nvcc, include/cuda_runtime.h, and libcudart.so was found." >&2
      return 1
    fi
  fi

  CUDAToolkit_ROOT="$CUDA_TOOLKIT_ROOT_RESOLVED"
  if [[ -n "$explicit_nvcc" ]]; then
    CUDACXX="$explicit_nvcc"
    CMAKE_CUDA_COMPILER="${CMAKE_CUDA_COMPILER:-$explicit_nvcc}"
  else
    CUDACXX="$CUDA_NVCC_REALPATH"
    CMAKE_CUDA_COMPILER="$CUDA_NVCC_REALPATH"
  fi

  local version_text version
  version_text="$($CUDA_NVCC_REALPATH --version 2>&1 || true)"
  version="$(sed -n 's/.*release \([^, ]*\).*/\1/p' <<<"$version_text" | head -n1)"
  CUDA_TOOLKIT_VERSION="${version:-$(tail -n1 <<<"$version_text")}"

  CUDA_DRIVER_LIBRARY="$(_cuda_find_driver_lib 2>/dev/null || true)"
  if [[ -z "${CUDA_PATH:-}" && -n "$CUDA_DRIVER_LIBRARY" ]]; then
    CUDA_PATH="$(dirname "$CUDA_DRIVER_LIBRARY")"
  fi
  export CUDAToolkit_ROOT CUDACXX CMAKE_CUDA_COMPILER \
    CUDA_TOOLKIT_ROOT_RESOLVED CUDA_NVCC_PATH CUDA_NVCC_REALPATH CUDA_RUNTIME_HEADER CUDA_CUDART_PATH CUDA_TOOLKIT_VERSION CUDA_DRIVER_LIBRARY CUDA_PATH
  return 0
}

_cuda_find_driver_lib() {
  local dir candidate
  for dir in \
    "${NVIDIA_DRIVER_LIB_DIR:-}" \
    /usr/local/nvidia/lib64 \
    /usr/lib/x86_64-linux-gnu \
    /usr/lib64 \
    /lib/x86_64-linux-gnu; do
    [[ -n "$dir" && -d "$dir" ]] || continue
    for candidate in "$dir/libcuda.so" "$dir/libcuda.so.1"; do
      if [[ -e "$candidate" ]]; then printf '%s\n' "$candidate"; return 0; fi
    done
  done
  return 1
}
