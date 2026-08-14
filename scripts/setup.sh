#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$PROJECT_ROOT/scripts/common.sh"
source "$PROJECT_ROOT/scripts/cuda_toolkit.sh"

SETUP_STARTED="$(monotonic_now)"
SETUP_STATE="$RUNTIME_STATE_DIR/setup.env"
VENV_REUSED=0
if [[ -x "$VENV_DIR/bin/python" ]] && "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
  VENV_REUSED=1
fi
VENV_BOOTSTRAP_SECONDS=0
RUNTIME_DISCOVERY_SECONDS=0
write_setup_state() {
  local total
  total="$(elapsed_since "$SETUP_STARTED")"
  {
    printf 'SETUP_TOTAL_SECONDS=%q\n' "$total"
    printf 'VENV_BOOTSTRAP_SECONDS=%q\n' "$VENV_BOOTSTRAP_SECONDS"
    printf 'RUNTIME_DISCOVERY_SECONDS=%q\n' "$RUNTIME_DISCOVERY_SECONDS"
    printf 'VENV_REUSED=%q\n' "$VENV_REUSED"
  } > "$SETUP_STATE"
}

echo '== Muse Glimmer GPU Lab: Kaggle T4x2 NVIDIA/CUDA reproducibility setup =='
case "${LLAMA_SOURCE_MODE:-auto}" in auto|kaggle|build) ;; *) echo 'ERROR: LLAMA_SOURCE_MODE must be auto|kaggle|build' >&2; exit 2;; esac

command -v python3 >/dev/null 2>&1 || { echo "ERROR: required command 'python3' is unavailable." >&2; exit 2; }
if ! resolve_nvidia_runtime; then
  echo 'ERROR: NVIDIA management runtime preflight failed. A Kaggle GPU session with an accessible NVIDIA driver is required.' >&2
  exit 2
fi
write_nvidia_runtime_state "$RUNTIME_STATE_DIR/nvidia.env"
echo "NVIDIA runtime: smi=$NVIDIA_SMI_PATH driver_lib=${NVIDIA_ML_LIBRARY:-loader-default} path_injected=$NVIDIA_RUNTIME_PATH_INJECTED ld_injected=$NVIDIA_RUNTIME_LD_LIBRARY_INJECTED"

export CUDA_VISIBLE_DEVICES
python3 "$PROJECT_ROOT/scripts/gpu_probe.py" --min-count "$GPU_REQUIRED_COUNT" --min-vram-mib "$GPU_MIN_VRAM_MIB"

venv_started="$(monotonic_now)"
PYTHON_BIN="$(command -v python3)" VENV_DIR="$VENV_DIR" bash "$PROJECT_ROOT/scripts/bootstrap_venv.sh"
# bootstrap_venv.sh seeds the system wrapt distribution only as an early-startup
# bridge for Kaggle sitecustomize. The locked requirements below then enforce
# the project runtime version (wrapt==2.3.0) inside the venv.
"$VENV_DIR/bin/python" -m pip install -q --requirement "$PROJECT_ROOT/config/requirements.lock"
VENV_BOOTSTRAP_SECONDS="$(elapsed_since "$venv_started")"

if [[ "$LLAMA_SOURCE_MODE" == auto || "$LLAMA_SOURCE_MODE" == kaggle ]]; then
  runtime_started="$(monotonic_now)"
  set +e
  bash "$PROJECT_ROOT/scripts/resolve_kaggle_llama.sh"
  kaggle_rc=$?
  set -e
  RUNTIME_DISCOVERY_SECONDS="$(elapsed_since "$runtime_started")"
  if (( kaggle_rc == 0 )); then
    write_setup_state
    echo 'Attached Kaggle llama.cpp runtime/source resolved successfully; upstream clone build skipped.'
    echo 'Setup complete.'
    exit 0
  fi
  if (( kaggle_rc == 26 )); then
    echo 'ERROR: attached source was found but CUDA toolkit preflight failed; fail-fast: not falling back to an upstream clone/build.' >&2
    exit 26
  fi
  if [[ "$LLAMA_SOURCE_MODE" == kaggle ]]; then
    echo "ERROR: LLAMA_SOURCE_MODE=kaggle but attached runtime/source was unavailable or incompatible (resolver exit=$kaggle_rc)." >&2
    exit "$kaggle_rc"
  fi
  echo "Kaggle runtime/source unavailable/incompatible (resolver exit=$kaggle_rc); falling back to configured upstream CUDA build."
fi

missing=()
for c in git cmake g++ make curl; do command -v "$c" >/dev/null 2>&1 || missing+=("$c"); done
if (( ${#missing[@]} )); then
  if command -v apt-get >/dev/null 2>&1 && [[ "$(id -u)" -eq 0 ]]; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential cmake git curl ca-certificates python3-pip zip
  fi
fi
for c in git cmake g++ make curl; do
  command -v "$c" >/dev/null 2>&1 || { echo "ERROR: fallback CUDA build requires '$c'." >&2; exit 2; }
done
if ! resolve_cuda_toolkit; then
  echo 'ERROR: fallback CUDA build cannot continue because CUDA toolkit preflight failed.' >&2
  exit 26
fi

source_snapshot="$(bash "$PROJECT_ROOT/scripts/checkout_llama_source.sh" \
  "$LLAMA_CPP_REPO" "$LLAMA_CPP_REF" "${LLAMA_CPP_EXPECTED_COMMIT:-}" "$LLAMA_DIR")"
if ! grep -q 'LLM_ARCH_MUSE_GLIMMER' "$LLAMA_DIR/src/llama-arch.cpp"; then echo 'ERROR: selected llama.cpp checkout lacks Muse Glimmer support.' >&2; exit 3; fi
if [[ -n "${LLAMA_CPP_EXPECTED_COMMIT:-}" ]]; then
  python3 "$PROJECT_ROOT/scripts/dflash2_source_contract.py" \
    --source "$LLAMA_DIR" \
    --expected-commit "$LLAMA_CPP_EXPECTED_COMMIT"
fi

build="$(llama_build_dir)"
args=(
  -S "$LLAMA_DIR" -B "$build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF
  -DGGML_CUDA=ON -DGGML_NATIVE=ON -DGGML_OPENMP=ON -DGGML_BLAS=OFF -DLLAMA_CURL=OFF
  "-DCMAKE_CUDA_ARCHITECTURES=$CUDA_ARCHITECTURES"
  "-DCUDAToolkit_ROOT=$CUDA_TOOLKIT_ROOT_RESOLVED"
  "-DCMAKE_CUDA_COMPILER=$CMAKE_CUDA_COMPILER"
)
source_build_cache_hit=0
if [[ -x "$build/bin/llama-server" && -x "$build/bin/llama-cli" && -x "$build/bin/llama-bench" ]]; then
  source_build_cache_hit=1
fi
source_build_started="$(monotonic_now)"
echo "Configuring fallback llama.cpp CUDA ref=$LLAMA_CPP_REF arch=$CUDA_ARCHITECTURES (cache_present=$source_build_cache_hit)"
cmake "${args[@]}"
jobs="$(nproc)"; (( jobs > 8 )) && jobs=8
cmake --build "$build" --config Release -j"$jobs" --target llama-server llama-cli llama-bench
source_build_seconds="$(elapsed_since "$source_build_started")"
for bin in llama-server llama-cli llama-bench; do [[ -x "$build/bin/$bin" ]] || { echo "ERROR missing $build/bin/$bin" >&2; exit 5; }; done

runtime_version="$("$build/bin/llama-cli" --version 2>&1 || true)"
source_snapshot="$(git -C "$LLAMA_DIR" rev-parse HEAD)"
source_hash="$(python3 "$PROJECT_ROOT/scripts/source_tree_fingerprint.py" --root "$LLAMA_DIR")"
printf -v cmake_args_text '%q ' "${args[@]}"; cmake_args_text="${cmake_args_text% }"
compiler="$(g++ --version 2>&1 | head -n1 || true)"
cuda_version="$("$CUDA_NVCC_REALPATH" --version 2>&1 | tail -n1 || true)"
{
  printf 'LLAMA_RESOLVED_BIN_DIR=%q\n' "$build/bin"
  printf 'LLAMA_RUNTIME_SOURCE=%q\n' local_build
  printf 'LLAMA_RUNTIME_LD_LIBRARY_PATH=%q\n' ""
  printf 'LLAMA_RUNTIME_DATASET_ROOT=%q\n' ""
  printf 'LLAMA_RUNTIME_VERSION_TEXT=%q\n' "$runtime_version"
  printf 'LLAMA_SOURCE_SNAPSHOT=%q\n' "$source_snapshot"
  printf 'LLAMA_SOURCE_PATH=%q\n' "$LLAMA_DIR"
  printf 'LLAMA_SOURCE_TREE_SHA256=%q\n' "$source_hash"
  printf 'LLAMA_BUILD_CMAKE_ARGS=%q\n' "$cmake_args_text"
  printf 'LLAMA_BUILD_COMPILER=%q\n' "$compiler"
  printf 'LLAMA_BUILD_CUDA_VERSION=%q\n' "$cuda_version"
  printf 'LLAMA_BUILD_DIR=%q\n' "$build"
  printf 'LLAMA_SOURCE_BUILD_SECONDS=%q\n' "$source_build_seconds"
  printf 'SOURCE_BUILD_CACHE_HIT=%q\n' "$source_build_cache_hit"
  printf 'CUDAToolkit_ROOT=%q\n' "${CUDAToolkit_ROOT:-}"
  printf 'CUDACXX=%q\n' "${CUDACXX:-}"
  printf 'CMAKE_CUDA_COMPILER=%q\n' "${CMAKE_CUDA_COMPILER:-}"
  printf 'CUDA_TOOLKIT_ROOT_RESOLVED=%q\n' "${CUDA_TOOLKIT_ROOT_RESOLVED:-}"
  printf 'CUDA_NVCC_PATH=%q\n' "${CUDA_NVCC_PATH:-}"
  printf 'CUDA_NVCC_REALPATH=%q\n' "${CUDA_NVCC_REALPATH:-}"
  printf 'CUDA_RUNTIME_HEADER=%q\n' "${CUDA_RUNTIME_HEADER:-}"
  printf 'CUDA_CUDART_PATH=%q\n' "${CUDA_CUDART_PATH:-}"
  printf 'CUDA_TOOLKIT_VERSION=%q\n' "${CUDA_TOOLKIT_VERSION:-}"
  printf 'CUDA_DRIVER_LIBRARY=%q\n' "${CUDA_DRIVER_LIBRARY:-}"
  printf 'CUDA_PATH=%q\n' "${CUDA_PATH:-}"
  printf 'LLAMA_BINARY_SHA256_SERVER=%q\n' "$(sha256sum "$build/bin/llama-server" | awk '{print $1}')"
  printf 'LLAMA_BINARY_SHA256_CLI=%q\n' "$(sha256sum "$build/bin/llama-cli" | awk '{print $1}')"
  printf 'LLAMA_BINARY_SHA256_BENCH=%q\n' "$(sha256sum "$build/bin/llama-bench" | awk '{print $1}')"
} > "$RUNTIME_STATE_DIR/llama.env"

"$build/bin/llama-cli" --version || true
"$build/bin/llama-cli" --list-devices || true
echo "llama.cpp commit: $source_snapshot"
echo 'selected runtime source: local_build'
write_setup_state
echo 'Setup complete.'
