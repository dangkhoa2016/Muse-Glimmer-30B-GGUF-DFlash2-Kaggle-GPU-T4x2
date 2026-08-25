#!/usr/bin/env bash
# Deterministic demo smoke harness (no real model / no GPU).
# Drives the real auth_proxy against a controlled fake loopback backend and
# asserts the full production-demo public contract: auth, allowlist, valid chat
# forwarding, SSE preservation, payload limits, busy 429, rate limit, timeouts,
# telemetry, and slot release. Exits non-zero on the first failing assertion.
set -Eeuo pipefail
set +x
export PYTHONDONTWRITEBYTECODE=1

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -f "$ROOT/scripts/auth_proxy.py" ]]; then
  echo "ERROR: cannot locate scripts/auth_proxy.py under $ROOT" >&2
  exit 64
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: demo-smoke.sh                # run the deterministic demo smoke suite
EOF
  exit 0
fi

# Make the modules under scripts importable when invoked from anywhere.
export PYTHONPATH="$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"

exec "$ROOT/tests/test_demo_smoke.py"