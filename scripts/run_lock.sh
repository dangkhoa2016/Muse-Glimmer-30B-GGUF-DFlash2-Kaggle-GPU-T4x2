#!/usr/bin/env bash
set -Eeuo pipefail

acquire_run_lock() {
  local lock_dir="${1:?lock directory required}" owner=""
  if mkdir "$lock_dir" 2>/dev/null; then
    printf '%s\n' "$$" > "$lock_dir/owner.pid"
    return 0
  fi

  [[ -f "$lock_dir/owner.pid" ]] && owner="$(cat "$lock_dir/owner.pid" 2>/dev/null || true)"
  if [[ "$owner" =~ ^[0-9]+$ ]] && kill -0 "$owner" 2>/dev/null; then
    echo "ERROR: another Muse-Glimmer run owns lock $lock_dir (pid=$owner)" >&2
    return 12
  fi

  rm -rf "$lock_dir"
  if ! mkdir "$lock_dir" 2>/dev/null; then
    echo "ERROR: could not acquire Muse-Glimmer run lock $lock_dir" >&2
    return 12
  fi
  printf '%s\n' "$$" > "$lock_dir/owner.pid"
}

release_run_lock() {
  local lock_dir="${1:?lock directory required}" owner=""
  [[ -d "$lock_dir" ]] || return 0
  [[ -f "$lock_dir/owner.pid" ]] && owner="$(cat "$lock_dir/owner.pid" 2>/dev/null || true)"
  if [[ -z "$owner" || "$owner" == "$$" ]]; then
    rm -rf "$lock_dir"
  fi
}
