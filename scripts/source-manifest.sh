#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cmd="${1:-check}"
case "$cmd" in
  check|write) exec python3 "$ROOT/scripts/source_manifest.py" "$cmd" --root "$ROOT" ;;
  *) echo "Usage: bash scripts/source-manifest.sh [check|write]" >&2; exit 2 ;;
esac
