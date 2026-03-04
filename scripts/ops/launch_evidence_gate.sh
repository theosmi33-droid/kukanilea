#!/usr/bin/env bash
set -euo pipefail

EXIT_USAGE=2
EXIT_DEPENDENCY=3
EXIT_GATE_FAIL=4

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="$ROOT/docs/reviews/codex"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$OUT_DIR/LAUNCH_EVIDENCE_RUN_${STAMP}.md"
DECISION_FILE="$OUT_DIR/LAUNCH_DECISION_${STAMP}.md"

FAST_MODE=0
SKIP_PYTEST=0
SKIP_HEALTHCHECK=0

FAIL_COUNT=0
PASS_COUNT=0
WARN_COUNT=0
REPO="${REPO:-}"

declare -a RESULT_LINES=()

die() {
  local code="$1"
  shift
  printf '[launch-evidence] ERROR: %s\n' "$*" >&2
  exit "$code"
}

log_info() {
  printf '[launch-evidence] %s\n' "$*" >&2
}

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

append() {
  printf '%s\n' "$*" >> "$OUT_FILE"
}

capture_cmd() {
  local cmd="$1"
  local outfile="$2"
  (cd "$ROOT" && bash -lc "$cmd") >"$outfile" 2>&1
}

render_output_block() {
  local path="$1"
  append '```text'
  if [[ -s "$path" ]]; then
    sed -n '1,220p' "$path" >> "$OUT_FILE"
  else
    append '(no output)'
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
    *) die "$EXIT_USAGE" "unknown result status '$status' for gate '$gate'" ;;
  esac
}

run_gate_simple() {
  local gate="$1"
  local cmd="$2"
  local failure_note="${3:-command failed}"
  local tmp
  tmp="$(mktemp)"
  append "## ${gate}"
  append "\`${cmd}\`"
  if capture_cmd "$cmd" "$tmp"; then
    render_output_block "$tmp"
    record_result "$gate" "PASS" "command succeeded"
  else
    render_output_block "$tmp"
    record_result "$gate" "FAIL" "$failure_note"
  fi
  rm -f "$tmp"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fast) FAST_MODE=1 ;;
    --skip-healthcheck) SKIP_HEALTHCHECK=1 ;;
    --skip-pytest) SKIP_PYTEST=1 ;;
    --out)
      shift
      [[ $# -gt 0 ]] || die "$EXIT_USAGE" "missing value for --out"
      OUT_FILE="$1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "$EXIT_USAGE" "unknown argument: $1"
      ;;
  esac
  shift
done

if [[ "$FAST_MODE" -eq 1 ]]; then
  SKIP_HEALTHCHECK=1
  SKIP_PYTEST=1
fi

for dep in rg git bash; do
  command -v "$dep" >/dev/null 2>&1 || die "$EXIT_DEPENDENCY" "required dependency missing: $dep"
done

if [[ -z "$REPO" ]]; then
  REPO="$(detect_repo || true)"
fi

mkdir -p "$(dirname "$OUT_FILE")"
mkdir -p "$OUT_DIR"

append "# KUKANILEA Launch Evidence Run"
append
append "- Timestamp: $(date -Iseconds)"
append "- Root: \`$ROOT\`"
append "- Host: \`$(hostname)\`"
append "- Repo: \`${REPO:-unknown}\`"
append

# Gate 1: Repo/CI evidence
_tmp="$(mktemp)"
append "## Repo/CI Evidence"
append '`git fetch origin --prune && echo "LOCAL=$(git rev-parse --short HEAD)" && echo "ORIGIN_MAIN=$(git rev-parse --short origin/main)"`'
if capture_cmd "git fetch origin --prune && echo \"LOCAL=$(git rev-parse --short HEAD)\" && echo \"ORIGIN_MAIN=$(git rev-parse --short origin/main)\"" "$_tmp"; then
  render_output_block "$_tmp"
  local_head="$(grep '^LOCAL=' "$_tmp" | head -n1 | cut -d= -f2-)"
  origin_head="$(grep '^ORIGIN_MAIN=' "$_tmp" | head -n1 | cut -d= -f2-)"
  if [[ -n "$local_head" && -n "$origin_head" ]]; then
    record_result "Repo/CI Evidence" "PASS" "repo heads resolved (LOCAL=${local_head}, ORIGIN_MAIN=${origin_head})"
  else
    record_result "Repo/CI Evidence" "FAIL" "missing LOCAL/ORIGIN_MAIN hashes"
  fi
else
  render_output_block "$_tmp"
  record_result "Repo/CI Evidence" "FAIL" "git fetch/rev-parse failed"
fi
rm -f "$_tmp"

if [[ -z "$REPO" ]]; then
  append "## Main CI Status"
  append "repo slug not detected"
  record_result "Main CI Status" "FAIL" "repo slug missing (set REPO=owner/name)"
elif command -v gh >/dev/null 2>&1; then
  run_gate_simple "Main CI Status" "gh run list --repo $REPO --branch main --limit 12 --json workflowName,displayTitle,headBranch,status,conclusion" "unable to query GitHub Actions runs"
else
  append "## Main CI Status"
  append "gh CLI missing"
  record_result "Main CI Status" "FAIL" "gh CLI missing (cannot prove CI state)"
fi

# Gate 2: Core Health
if [[ "$SKIP_HEALTHCHECK" -eq 1 ]]; then
  record_result "Core Health" "WARN" "skipped by flag"
else
  run_gate_simple "Core Health" "./scripts/ops/healthcheck.sh" "core healthcheck failed"
fi

# Gate 3: Zero-CDN scan
run_gate_simple "Zero-CDN Scan" "python3 scripts/ops/verify_guardrails.py" "guardrails verification failed"

# Gate 4: White-Mode evidence
_tmp="$(mktemp)"
append "## White-Mode Evidence"
DARK_PATTERN="dark:|themeToggle|classList\\.(add|toggle)\\((\"dark\"|'dark')\\)"
append "\`rg -n \"$DARK_PATTERN\" app/templates app/static --glob '!app/static/vendor/**' --glob '!app/static/js/tailwindcss.min.js' || true\`"
capture_cmd "rg -n \"$DARK_PATTERN\" app/templates app/static --glob '!app/static/vendor/**' --glob '!app/static/js/tailwindcss.min.js' || true" "$_tmp"
render_output_block "$_tmp"
if [[ ! -s "$_tmp" ]]; then
  record_result "White-Mode Evidence" "PASS" "no dark mode toggle signatures found"
else
  record_result "White-Mode Evidence" "FAIL" "dark mode signatures found"
fi
rm -f "$_tmp"

# Gate 5: Chat/Guardrail evidence
_tmp="$(mktemp)"
append "## Chat/Guardrail Evidence"
append '`rg -n "chat|messenger|guardrail|policy" app/templates app/static/js scripts/ops/verify_guardrails.py || true`'
capture_cmd "rg -n 'chat|messenger|guardrail|policy' app/templates app/static/js scripts/ops/verify_guardrails.py || true" "$_tmp"
render_output_block "$_tmp"
if [[ -s "$_tmp" ]]; then
  record_result "Chat/Guardrail Evidence" "PASS" "chat/guardrail markers detected"
else
  record_result "Chat/Guardrail Evidence" "FAIL" "no chat/guardrail evidence markers detected"
fi
rm -f "$_tmp"

# Extra checks
run_gate_simple "VSCode Guardrails" "bash scripts/dev/vscode_guardrails.sh --check" "vscode guardrails check failed"
run_gate_simple "Overlap Matrix" "bash scripts/orchestration/overlap_matrix_11.sh" "overlap matrix script failed"

if [[ "$SKIP_PYTEST" -eq 1 ]]; then
  record_result "Pytest" "WARN" "skipped by flag"
else
  run_gate_simple "Pytest" "pytest -q" "pytest execution failed"
fi

run_gate_simple "KPI Snapshot" "./scripts/ops/kpi_snapshot.sh" "kpi snapshot failed"

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
    DECISION="GO"
  else
    DECISION="GO with Notes"
  fi
else
  DECISION="NO-GO"
fi
append "**${DECISION}**"
append
append "- PASS: ${PASS_COUNT}"
append "- WARN: ${WARN_COUNT}"
append "- FAIL: ${FAIL_COUNT}"

EVIDENCE_REL_PATH="$(realpath --relative-to="$ROOT" "$OUT_FILE" 2>/dev/null || echo "$OUT_FILE")"

cat > "$DECISION_FILE" <<DECISION_DOC
# Launch Decision (${STAMP})

- Decision: **${DECISION}**
- Evidence file: \`${EVIDENCE_REL_PATH}\`
- PASS: ${PASS_COUNT}
- WARN: ${WARN_COUNT}
- FAIL: ${FAIL_COUNT}

## Gate Failures
$(for line in "${RESULT_LINES[@]}"; do
  case "$line" in
    *"| FAIL |"*) printf -- "- %s\n" "$line" ;;
  esac
done)
DECISION_DOC

log_info "Evidence report written to: $OUT_FILE"
log_info "Decision report written to: $DECISION_FILE"
printf '%s\n' "$OUT_FILE"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit "$EXIT_GATE_FAIL"
fi
