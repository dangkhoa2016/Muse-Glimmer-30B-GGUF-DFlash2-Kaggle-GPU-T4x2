#!/usr/bin/env bash
set -Eeuo pipefail

repo="${1:?repository URL required}"
ref="${2:?source ref required}"
expected="${3-}"
dest="${4:?destination required}"

if [[ -n "$expected" && ! "$expected" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: expected llama.cpp commit must be a full 40-character SHA: $expected" >&2
  exit 2
fi

if [[ ! -d "$dest/.git" ]]; then
  mkdir -p "$dest"
  git -C "$dest" init -q
fi

git -C "$dest" fetch --depth 1 "$repo" "$ref"
git -C "$dest" checkout --detach --force -q FETCH_HEAD
resolved="$(git -C "$dest" rev-parse HEAD)"
if [[ -n "$expected" && "$resolved" != "$expected" ]]; then
  echo "ERROR: llama.cpp commit mismatch: expected=$expected resolved=$resolved" >&2
  exit 3
fi
printf '%s\n' "$resolved"
