#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/common.sh"
case "${SOURCE_INTEGRITY_MODE:-strict}" in
  off) exit 0 ;;
  warn)
    if ! python3 "$ROOT/scripts/source_manifest.py" check --root "$ROOT"; then
      echo "WARNING: source manifest mismatch; continuing because SOURCE_INTEGRITY_MODE=warn" >&2
    fi ;;
  strict) python3 "$ROOT/scripts/source_manifest.py" check --root "$ROOT" ;;
  *) echo "ERROR: SOURCE_INTEGRITY_MODE must be strict, warn, or off" >&2; exit 2 ;;
esac
