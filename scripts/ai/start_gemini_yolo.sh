#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea/kukanilea_production"
REF_STACK="$ROOT/docs/ai/GEMINI_REFERENCE_STACK.md"
ALIGNMENT="$ROOT/docs/ai/GEMINI_ALIGNMENT_PROMPT.md"
MODEL="${GEMINI_MODEL:-gemini-3-flash-preview}"
MODE="interactive"
UPDATE_EXTENSIONS="0"
USER_PROMPT_FILE=""

usage() {
  cat <<'EOF'
Usage: start_gemini_yolo.sh [--check] [--headless-test] [--update-extensions] [--prompt-file <file>]

Options:
  --check               Validate environment only (no Gemini session start)
  --headless-test       Run a one-shot headless Gemini test in YOLO mode
  --update-extensions   Update extension hints (code-review + mcp-toolbox-for-databases)
  --prompt-file <file>  Append a task prompt to the base KUKANILEA boot prompt
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      MODE="check"
      shift
      ;;
    --headless-test)
      MODE="headless"
      shift
      ;;
    --update-extensions)
      UPDATE_EXTENSIONS="1"
      shift
      ;;
    --prompt-file)
      USER_PROMPT_FILE="${2:-}"
      if [[ -z "$USER_PROMPT_FILE" ]]; then
        echo "Missing value for --prompt-file" >&2
        exit 2
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

normalize_token() {
  # Remove accidental "Bearer " prefix and surrounding spaces.
  echo "${1:-}" | sed -E 's/^[[:space:]]*Bearer[[:space:]]+//' | sed -E 's/^[[:space:]]+|[[:space:]]+$//g'
}

ensure_auth_env() {
  local gh_token=""
  gh_token="$(gh auth token 2>/dev/null || true)"
  gh_token="$(normalize_token "$gh_token")"
  if [[ -z "$gh_token" ]]; then
    echo "No GitHub token available from gh auth. Run: gh auth login" >&2
    exit 1
  fi

  export GITHUB_MCP_PAT="$(normalize_token "${GITHUB_MCP_PAT:-$gh_token}")"
  export GITHUB_TOKEN="$(normalize_token "${GITHUB_TOKEN:-$gh_token}")"
  export GH_TOKEN="$(normalize_token "${GH_TOKEN:-$gh_token}")"
}

validate_files() {
  local missing=0
  for f in "$REF_STACK" "$ALIGNMENT"; do
    if [[ ! -f "$f" ]]; then
      echo "Missing reference file: $f" >&2
      missing=1
    fi
  done
  if [[ "$missing" -ne 0 ]]; then
    exit 1
  fi

  local found_refs=0
  local ref_path=""
  while IFS= read -r ref_path; do
    if [[ -f "$ref_path" ]]; then
      found_refs=$((found_refs + 1))
    else
      echo "Warning: reference file not found: $ref_path" >&2
    fi
  done < <(sed -nE 's/^[0-9]+\.[[:space:]]+`(\/.*)`$/\1/p' "$REF_STACK")

  if [[ "$found_refs" -eq 0 ]]; then
    echo "No usable reference files found in: $REF_STACK" >&2
    exit 1
  fi
}

print_support_stack() {
  cat <<EOF
== Gemini Support Stack ==
- $ALIGNMENT
- $REF_STACK
EOF
}

preflight() {
  require_cmd gemini
  require_cmd gh
  require_cmd rg

  cd "$ROOT"
  validate_files
  ensure_auth_env

  echo "Gemini version: $(gemini --version)"
  echo "Model: $MODEL"
  echo "Auth lengths: GITHUB_MCP_PAT=${#GITHUB_MCP_PAT}, GITHUB_TOKEN=${#GITHUB_TOKEN}, GH_TOKEN=${#GH_TOKEN}"

  if [[ "$UPDATE_EXTENSIONS" == "1" ]]; then
    gemini extensions update code-review || true
    gemini extensions update mcp-toolbox-for-databases || true
  fi

  local mcp_status
  mcp_status="$(gemini mcp list 2>&1 || true)"
  echo "$mcp_status"
  if ! grep -q "github (from github): .*Connected" <<<"$mcp_status"; then
    echo "GitHub MCP is not connected. Check token and extension config." >&2
    exit 1
  fi

  print_support_stack
}

build_boot_prompt() {
  cat <<EOF
Du arbeitest im KUKANILEA-Core. Nutze folgende Referenzquellen als verbindliche Stuetze:
1) $ALIGNMENT
2) $REF_STACK

Arbeitsmodus:
- Keine Aenderung ausserhalb der Domain-Allowlist ohne Scope-Request.
- Zero-CDN, White-Mode-only, HTMX-Shell-Kontrakt einhalten.
- Bei jeder Empfehlung explizit mindestens eine Referenzdatei nennen.

Antworte zu Beginn mit:
READY: KUKANILEA YOLO with reference stack loaded.
EOF
}

compose_prompt() {
  local base_prompt
  base_prompt="$(build_boot_prompt)"
  if [[ -n "$USER_PROMPT_FILE" ]]; then
    if [[ ! -f "$USER_PROMPT_FILE" ]]; then
      echo "Prompt file not found: $USER_PROMPT_FILE" >&2
      exit 1
    fi
    printf "%s\n\n## ARBEITSAUFTRAG\n%s\n" "$base_prompt" "$(cat "$USER_PROMPT_FILE")"
    return
  fi
  printf "%s\n" "$base_prompt"
}

run_headless_test() {
  local prompt
  prompt="$(compose_prompt)"
  gemini -p "$prompt"$'\n\nAntwort nur exakt mit: OK' \
    --approval-mode yolo \
    --output-format text \
    -m "$MODEL"
}

run_interactive() {
  local prompt
  prompt="$(compose_prompt)"
  gemini --prompt-interactive "$prompt" --approval-mode yolo -m "$MODEL"
}

preflight

case "$MODE" in
  check)
    echo "Preflight passed."
    ;;
  headless)
    run_headless_test
    ;;
  interactive)
    run_interactive
    ;;
esac
