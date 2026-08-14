#!/usr/bin/env bash
set -Eeuo pipefail
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:?VENV_DIR must be set}"

if [[ -x "$VENV_DIR/bin/python" ]] && "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
  echo "Existing venv is usable: $VENV_DIR"
  exit 0
fi

rm -rf "$VENV_DIR"
mkdir -p "$(dirname "$VENV_DIR")"
echo "Creating venv: $VENV_DIR"
if "$PYTHON_BIN" -m venv "$VENV_DIR"; then
  :
else
  echo 'Normal venv creation failed (likely missing ensurepip); retrying with --without-pip.' >&2
  rm -rf "$VENV_DIR"
  "$PYTHON_BIN" -m venv --without-pip "$VENV_DIR"
fi

# Do not start the new interpreter yet. Kaggle's global sitecustomize imports
# wrapt, while an isolated fresh venv does not initially contain it. Compute
# the venv site-packages path from the creating/system interpreter instead.
target_site="$("$PYTHON_BIN" - "$VENV_DIR" <<'PYTARGET'
import sysconfig
import sys

venv_dir = sys.argv[1]
print(sysconfig.get_path('purelib', vars={'base': venv_dir, 'platbase': venv_dir}))
PYTARGET
)"
mkdir -p "$target_site"

seed_system_distribution() {
  local distribution="$1"
  local required="$2"
  "$PYTHON_BIN" - "$target_site" "$distribution" "$required" <<'PYSEED'
import importlib.metadata
import shutil
import sys
from pathlib import Path

target = Path(sys.argv[1])
name = sys.argv[2]
required = sys.argv[3] == '1'
try:
    dist = importlib.metadata.distribution(name)
except importlib.metadata.PackageNotFoundError:
    if required:
        raise SystemExit(f"system Python distribution {name!r} is required for venv bootstrap")
    raise SystemExit(20)

package_root = name.replace('-', '_')
normalized = name.replace('_', '-').lower()
copied = 0
for entry in dist.files or []:
    rel = Path(str(entry))
    if not rel.parts or '..' in rel.parts:
        continue
    first = rel.parts[0]
    first_lower = first.lower()
    is_package = first == package_root
    is_dist_info = first_lower.startswith(normalized + '-') and first_lower.endswith('.dist-info')
    if not (is_package or is_dist_info):
        continue
    src = Path(dist.locate_file(entry))
    dst = target / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        shutil.copy2(src, dst)
        copied += 1
if copied == 0:
    raise SystemExit(f"system {name} metadata contained no copyable package files")
print(f"Seeded system {name} {dist.version} into fresh venv bootstrap site-packages.")
PYSEED
}

# Kaggle's /etc/python*/sitecustomize.py imports wrapt before project
# requirements are installed. Seed the already-working system distribution
# into the isolated venv so the very first normal venv startup is clean.
set +e
seed_system_distribution wrapt 0
wrapt_seed_rc=$?
set -e
if (( wrapt_seed_rc != 0 && wrapt_seed_rc != 20 )); then
  exit "$wrapt_seed_rc"
fi

if ! "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
  echo 'Bootstrapping pip into ensurepip-less venv from the system pip installation.'
  seed_system_distribution pip 1
fi

"$VENV_DIR/bin/python" -m pip --version >/dev/null
