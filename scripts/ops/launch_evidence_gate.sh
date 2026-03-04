#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="$ROOT/docs/reviews/codex"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$OUT_DIR/LAUNCH_EVIDENCE_RUN_${STAMP}.md"

FAST_MODE=0
SKIP_PYTEST=0
SKIP_HEALTHCHECK=0

FAIL_COUNT=0
PASS_COUNT=0
WARN_COUNT=0
REPO="${REPO:-}"

declare -a RESULT_LINES=()

usage() {
  cat <<'USAGE'
Usage: scripts/ops/launch_evidence_gate.sh [options]

Options:
  --fast              Skip heavy checks (healthcheck + pytest)
  --skip-healthcheck  Skip ./scripts/ops/healthcheck.sh
  --skip-pytest       Skip pytest -q
  --out <path>        Custom markdown output path
  --help              Show this help
USAGE
}

detect_repo() {
  local repo=""
  local remote_url=""

  if command -v gh >/dev/null 2>&1; then
    repo="$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || true)"
    if [[ -n "$repo" ]]; then
      printf '%s\n' "$repo"
      return 0
    fi
  fi

  remote_url="$(git -C "$ROOT" config --get remote.origin.url 2>/dev/null || true)"
  if [[ "$remote_url" =~ github\.com[:/]([^/]+/[^/.]+)(\.git)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi

  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fast) FAST_MODE=1 ;;
    --skip-healthcheck) SKIP_HEALTHCHECK=1 ;;
    --skip-pytest) SKIP_PYTEST=1 ;;
    --out)
      shift
      if [[ $# -eq 0 ]]; then
        echo "missing value for --out" >&2
        exit 2
      fi
      OUT_FILE="$1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
  shift
done

if [[ "$FAST_MODE" -eq 1 ]]; then
  SKIP_HEALTHCHECK=1
  SKIP_PYTEST=1
fi

if ! command -v rg >/dev/null 2>&1; then
  echo "Error: rg (ripgrep) is not installed. Please install it to continue." >&2
  exit 1
fi

if [[ -z "$REPO" ]]; then
  REPO="$(detect_repo || true)"
fi

if [[ -z "$REPO" ]]; then
  echo "Error: unable to detect GitHub repository slug. Set REPO=owner/name." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT_FILE")"

append() {
  printf '%s\n' "$*" >> "$OUT_FILE"
}

capture_cmd() {
  local cmd="$1"
  local outfile="$2"
  (cd "$ROOT" && bash -lc "$cmd") >"$outfile" 2>&1
  return $?
}

render_output_block() {
  local path="$1"
  append '```text'
  if [[ -s "$path" ]]; then
    sed -n '1,200p' "$path" >> "$OUT_FILE"
  else
    append "(no output)"
  fi
  append '```'
}

record_result() {
  local gate="$1"
  local status="$2"
  local note="$3"
  RESULT_LINES+=("| ${gate} | ${status} | ${note} |")
  case "$status" in
    PASS) PASS_COUNT=$((PASS_COUNT + 1)) ;;
    WARN) WARN_COUNT=$((WARN_COUNT + 1)) ;;
    FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
  esac
}

run_gate_simple() {
  local gate="$1"
  local cmd="$2"
  local tmp
  tmp="$(mktemp)"
  append "## ${gate}"
  append "\`$cmd\`"
  if capture_cmd "$cmd" "$tmp"; then
    render_output_block "$tmp"
    record_result "$gate" "PASS" "command succeeded"
  else
    render_output_block "$tmp"
    record_result "$gate" "FAIL" "command failed"
  fi
  rm -f "$tmp"
}

append "# KUKANILEA Launch Evidence Run"
append
append "- Timestamp: $(date -Iseconds)"
append "- Root: \`$ROOT\`"
append "- Host: \`$(hostname)\`"
append

# Gate 1: Repo sync
tmp="$(mktemp)"
append "## Repo Sync"
append '`git fetch origin --prune && git rev-parse --short HEAD && git rev-parse --short origin/main`'
if capture_cmd "git fetch origin --prune && echo \"LOCAL=$(git rev-parse --short HEAD)\" && echo \"ORIGIN_MAIN=$(git rev-parse --short origin/main)\"" "$tmp"; then
  render_output_block "$tmp"
  local_head="$(grep '^LOCAL=' "$tmp" | head -n1 | cut -d= -f2-)"
  origin_head="$(grep '^ORIGIN_MAIN=' "$tmp" | head -n1 | cut -d= -f2-)"
  if [[ -n "$local_head" && -n "$origin_head" && "$local_head" == "$origin_head" ]]; then
    record_result "Repo Sync" "PASS" "LOCAL == ORIGIN_MAIN (${local_head})"
  else
    record_result "Repo Sync" "FAIL" "LOCAL (${local_head:-?}) != ORIGIN_MAIN (${origin_head:-?})"
  fi
else
  render_output_block "$tmp"
  record_result "Repo Sync" "FAIL" "git fetch/rev-parse failed"
fi
rm -f "$tmp"

# Gate 2: Open PRs
if command -v gh >/dev/null 2>&1; then
  tmp="$(mktemp)"
  append "## Open PRs"
  append "\`gh pr list --repo $REPO --state open --json number,title,headRefName\`"
  if capture_cmd "gh pr list --repo $REPO --state open --json number,title,headRefName" "$tmp"; then
    render_output_block "$tmp"
    if command -v jq >/dev/null 2>&1; then
      pr_count="$(jq 'length' "$tmp" 2>/dev/null || echo "9999")"
      if [[ "$pr_count" == "0" ]]; then
        record_result "Open PRs" "PASS" "no open pull requests"
      else
        record_result "Open PRs" "FAIL" "${pr_count} open pull requests"
      fi
    else
      record_result "Open PRs" "WARN" "jq missing; count not validated"
    fi
  else
    render_output_block "$tmp"
    record_result "Open PRs" "FAIL" "gh pr list failed"
  fi
  rm -f "$tmp"
else
  append "## Open PRs"
  append "gh not installed"
  record_result "Open PRs" "FAIL" "gh missing"
fi

# Gate 3: Main CI summary
if command -v gh >/dev/null 2>&1; then
  tmp="$(mktemp)"
  append "## Main CI Status"
  append "\`gh run list --repo $REPO --branch main --limit 12 --json workflowName,displayTitle,headBranch,status,conclusion\`"
  if capture_cmd "gh run list --repo $REPO --branch main --limit 12 --json workflowName,displayTitle,headBranch,status,conclusion" "$tmp"; then
    render_output_block "$tmp"
    if command -v jq >/dev/null 2>&1; then
      if main_count="$(jq 'length' "$tmp" 2>/dev/null)" && bad_count="$(jq '[.[] | select(.status!="completed" or .conclusion!="success")] | length' "$tmp" 2>/dev/null)"; then
        if [[ "$main_count" == "0" ]]; then
          record_result "Main CI Status" "WARN" "no main runs in last 12"
        elif [[ "$bad_count" == "0" ]]; then
          record_result "Main CI Status" "PASS" "all listed main runs successful"
        else
          record_result "Main CI Status" "FAIL" "${bad_count} main runs are not success"
        fi
      else
        record_result "Main CI Status" "WARN" "unable to parse gh run JSON output"
      fi
    else
      record_result "Main CI Status" "WARN" "jq missing; status not fully validated"
    fi
  else
    render_output_block "$tmp"
    record_result "Main CI Status" "FAIL" "gh run list failed"
  fi
  rm -f "$tmp"
fi

# Gate 4: VS Code guardrails
run_gate_simple "VSCode Guardrails" "bash scripts/dev/vscode_guardrails.sh --check"

# Gate 5: Overlap matrix (and simple parse)
tmp="$(mktemp)"
append "## Overlap Matrix"
append '`bash scripts/orchestration/overlap_matrix_11.sh`'
if capture_cmd "bash scripts/orchestration/overlap_matrix_11.sh" "$tmp"; then
  render_output_block "$tmp"
  matrix_path="$(tail -n1 "$tmp" | tr -d '\r')"
  if [[ -f "$matrix_path" ]]; then
    overlap_bad="$(rg -n 'MISSING_WORKTREE|ERROR|DOMAIN_OVERLAP_DETECTED|FAIL' "$matrix_path" | wc -l | tr -d ' ')"
    if [[ "$overlap_bad" == "0" ]]; then
      record_result "Overlap Matrix" "PASS" "no fail markers in ${matrix_path}"
    else
      record_result "Overlap Matrix" "FAIL" "${overlap_bad} fail markers in ${matrix_path}"
    fi
  else
    record_result "Overlap Matrix" "FAIL" "matrix output path missing"
  fi
else
  render_output_block "$tmp"
  record_result "Overlap Matrix" "FAIL" "script failed"
fi
rm -f "$tmp"

# Gate 6: Healthcheck
if [[ "$SKIP_HEALTHCHECK" -eq 1 ]]; then
  record_result "Healthcheck" "WARN" "skipped by flag"
else
  run_gate_simple "Healthcheck" "./scripts/ops/healthcheck.sh"
fi

# Gate 7: Pytest
if [[ "$SKIP_PYTEST" -eq 1 ]]; then
  record_result "Pytest" "WARN" "skipped by flag"
else
  run_gate_simple "Pytest" "pytest -q"
fi

# Gate 8: Guardrails (includes Zero-CDN checks)
tmp="$(mktemp)"
append "## Guardrails Verify"
append '`python scripts/ops/verify_guardrails.py`'
if capture_cmd "python scripts/ops/verify_guardrails.py" "$tmp"; then
  render_output_block "$tmp"
  record_result "Zero-CDN Scan" "PASS" "guardrails verification passed"
else
  render_output_block "$tmp"
  record_result "Zero-CDN Scan" "FAIL" "guardrails verification failed"
fi
rm -f "$tmp"

# Gate 9: Dark mode scan
tmp="$(mktemp)"
append "## White-Mode Scan"
DARK_PATTERN="dark:|themeToggle|classList\\.(add|toggle)\\((\"dark\"|'dark')\\)"
append "\`rg -n \"$DARK_PATTERN\" app/templates app/static --glob \"!app/static/vendor/**\" --glob \"!app/static/js/tailwindcss.min.js\" || true\`"
capture_cmd "rg -n \"$DARK_PATTERN\" app/templates app/static --glob '!app/static/vendor/**' --glob '!app/static/js/tailwindcss.min.js' || true" "$tmp"
render_output_block "$tmp"
if [[ ! -s "$tmp" ]]; then
  record_result "White-Mode Scan" "PASS" "no dark-mode toggles/patterns found"
else
  record_result "White-Mode Scan" "WARN" "dark-mode related pattern(s) present"
fi
rm -f "$tmp"

tmp="$(mktemp)"
append "## Color-Scheme Info Scan"
append '`rg -n "prefers-color-scheme" app/templates app/static --glob "!app/static/vendor/**" --glob "!app/static/js/tailwindcss.min.js" || true`'
capture_cmd "rg -n \"prefers-color-scheme\" app/templates app/static --glob '!app/static/vendor/**' --glob '!app/static/js/tailwindcss.min.js' || true" "$tmp"
render_output_block "$tmp"
if [[ -s "$tmp" ]]; then
  record_result "Color-Scheme Info Scan" "WARN" "prefers-color-scheme references present (review manually)"
else
  record_result "Color-Scheme Info Scan" "PASS" "no prefers-color-scheme references found"
fi
rm -f "$tmp"

# Gate 10: HTMX shell markers
tmp="$(mktemp)"
append "## HTMX Shell Scan"
append '`rg -n "hx-get|hx-target|hx-push-url" app/templates/layout.html app/templates -g "*.html" || true`'
capture_cmd "rg -n \"hx-get|hx-target|hx-push-url\" app/templates/layout.html app/templates -g \"*.html\" || true" "$tmp"
render_output_block "$tmp"
if [[ -s "$tmp" ]]; then
  record_result "HTMX Shell Scan" "PASS" "htmx markers found"
else
  record_result "HTMX Shell Scan" "WARN" "no htmx markers found by scan"
fi
rm -f "$tmp"

# Gate 11: Branch protection setting
if command -v gh >/dev/null 2>&1; then
  tmp="$(mktemp)"
  append "## Branch Protection"
  append "\`gh api repos/$REPO/branches/main/protection --jq \".required_pull_request_reviews.required_approving_review_count\"\`"
  if capture_cmd "gh api repos/$REPO/branches/main/protection --jq '.required_pull_request_reviews.required_approving_review_count'" "$tmp"; then
    render_output_block "$tmp"
    approvals="$(tr -d ' \r\n' < "$tmp")"
    if [[ "$approvals" == "1" ]]; then
      record_result "Branch Protection" "PASS" "required approvals = 1"
    else
      record_result "Branch Protection" "WARN" "required approvals = ${approvals:-unknown}"
    fi
  else
    render_output_block "$tmp"
    record_result "Branch Protection" "WARN" "could not query branch protection"
  fi
  rm -f "$tmp"
fi

append
append "## Result Matrix"
append
append "| Gate | Status | Note |"
append "|---|---|---|"
for line in "${RESULT_LINES[@]}"; do
  append "$line"
done

append
append "## Decision"
append
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  if [[ "$WARN_COUNT" -eq 0 ]]; then
    append "**GO**"
  else
    append "**GO with Notes**"
  fi
else
  append "**NO-GO**"
fi
append
append "- PASS: ${PASS_COUNT}"
append "- WARN: ${WARN_COUNT}"
append "- FAIL: ${FAIL_COUNT}"

echo "$OUT_FILE"
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
