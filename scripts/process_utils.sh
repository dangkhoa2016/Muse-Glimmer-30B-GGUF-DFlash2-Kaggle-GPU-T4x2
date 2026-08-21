#!/usr/bin/env bash
# Process lifecycle helpers. Safe to source from set -Eeuo pipefail callers.

terminate_process() {
  local pid="${1:-}" timeout="${2:-5}" polls i
  [[ -n "$pid" ]] || return 0
  kill -0 "$pid" 2>/dev/null || { wait "$pid" 2>/dev/null || true; return 0; }
  kill -TERM "$pid" 2>/dev/null || true
  polls="$(awk -v t="$timeout" 'BEGIN { if (t < 0) t=0; n=int(t/0.05); if (n*0.05 < t) n++; if (n < 1) n=1; print n }')"
  for (( i=0; i<polls; i++ )); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.05
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
  wait "$pid" 2>/dev/null || true
}
