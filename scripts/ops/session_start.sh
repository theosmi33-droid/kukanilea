#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
SHARED_CLI="${REPO_ROOT}/scripts/shared_memory.py"
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
Usage:
  session_start.sh --domain <domain> [options]

Options:
  --actor <name>         Default: codex
  --source <name>        Default: codex
  --branch <name>        Default: auto-detect from git in --worktree
  --worktree <path>      Default: current directory
  --note <text>          Default: active_work
  --session-id <id>      Optional predefined session id
  --minutes <n>          Lock TTL in minutes, default: 120
  --reason <text>        Lock reason, default: active_work
  --db <path>            Optional explicit shared DB path
EOF
}

DOMAIN=""
ACTOR="codex"
SOURCE="codex"
BRANCH=""
WORKTREE="$(pwd -P)"
NOTE="active_work"
SESSION_ID=""
MINUTES="120"
REASON="active_work"
DB_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --actor) ACTOR="${2:-}"; shift 2 ;;
    --source) SOURCE="${2:-}"; shift 2 ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    --worktree) WORKTREE="${2:-}"; shift 2 ;;
    --note) NOTE="${2:-}"; shift 2 ;;
    --session-id) SESSION_ID="${2:-}"; shift 2 ;;
    --minutes) MINUTES="${2:-}"; shift 2 ;;
    --reason) REASON="${2:-}"; shift 2 ;;
    --db) DB_PATH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${DOMAIN}" ]]; then
  echo "--domain is required" >&2
  usage
  exit 2
fi

if [[ -z "${BRANCH}" ]]; then
  BRANCH="$(git -C "${WORKTREE}" symbolic-ref --short -q HEAD 2>/dev/null || true)"
  if [[ -z "${BRANCH}" ]]; then
    BRANCH="detached"
  fi
fi

db_args=()
if [[ -n "${DB_PATH}" ]]; then
  db_args=(--db "${DB_PATH}")
fi

start_args=(
  "${PYTHON_BIN}" "${SHARED_CLI}" "${db_args[@]}" start-session
  --actor "${ACTOR}"
  --source "${SOURCE}"
  --domain "${DOMAIN}"
  --branch "${BRANCH}"
  --worktree "${WORKTREE}"
  --note "${NOTE}"
)
if [[ -n "${SESSION_ID}" ]]; then
  start_args+=(--session-id "${SESSION_ID}")
fi

start_json="$("${start_args[@]}")"
resolved_session_id="$(printf '%s' "${start_json}" | "${PYTHON_BIN}" -c 'import json,sys; print(json.load(sys.stdin)["session_id"])')"

"${PYTHON_BIN}" "${SHARED_CLI}" "${db_args[@]}" lock-domain \
  --domain "${DOMAIN}" \
  --session-id "${resolved_session_id}" \
  --actor "${ACTOR}" \
  --source "${SOURCE}" \
  --minutes "${MINUTES}" \
  --reason "${REASON}" >/dev/null

printf '%s\n' "${resolved_session_id}"
