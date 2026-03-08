#!/usr/bin/env bash

main_only_preflight() {
  local root="$1"
  cd "$root"

  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[error] main-only preflight requires a git repository." >&2
    return 2
  fi

  local current_branch
  current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [[ "$current_branch" != "main" ]]; then
    echo "[error] main-only policy active: current branch is '$current_branch' (expected 'main')." >&2
    return 2
  fi

  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "[error] working tree has local changes. commit/stash first for clean launcher execution." >&2
    return 2
  fi

  if ! git show-ref --verify --quiet refs/remotes/origin/main; then
    echo "[warn] origin/main ref not available locally; skipping sync check." >&2
    return 0
  fi

  local counts ahead behind
  counts="$(git rev-list --left-right --count HEAD...origin/main 2>/dev/null || echo '0 0')"
  ahead="${counts%% *}"
  behind="${counts##* }"
  if [[ "$ahead" != "0" || "$behind" != "0" ]]; then
    echo "[error] main-only policy active: local main not synced with origin/main (ahead=$ahead, behind=$behind)." >&2
    echo "[hint] run 'git fetch origin --prune && git pull --ff-only origin main' before launcher start." >&2
    return 2
  fi

  return 0
}
