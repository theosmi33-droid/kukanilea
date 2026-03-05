#!/usr/bin/env bash
set -euo pipefail

EXIT_GO=0
EXIT_WARN=2
EXIT_NO_GO=3
EXIT_USAGE=64
EXIT_DEPENDENCY=69

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="$ROOT/docs/reviews/codex"
OUT_FILE="$OUT_DIR/LAUNCH_GATE_AUTOMATION_REPORT_20260305.md"
JSON_FILE="$OUT_DIR/LAUNCH_GATE_AUTOMATION_REPORT_20260305.json"
PYTHON="${PYTHON:-}"
REPO="${REPO:-}"

SKIP_HEALTHCHECK=0

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
DECISION="GO"
EXIT_CODE="$EXIT_GO"

declare -a GATE_NAMES=()
declare -a GATE_STATUS=()
declare -a GATE_NOTES=()

die() {
  local code="$1"
  shift
  printf '[launch-evidence] ERROR: %s\n' "$*" >&2
  exit "$code"
}

usage() {
  cat <<'USAGE'
Usage: scripts/ops/launch_evidence_gate.sh [options]

Options:
  --skip-healthcheck  Skip ./scripts/ops/healthcheck.sh
  --out <path>        Custom markdown output path
  --json-out <path>   Custom JSON output path
  --help              Show this help
USAGE
}

record_result() {
  local name="$1"
  local status="$2"
  local note="$3"
  GATE_NAMES+=("$name")
  GATE_STATUS+=("$status")
  GATE_NOTES+=("$note")

  case "$status" in
    PASS) PASS_COUNT=$((PASS_COUNT + 1)) ;;
    WARN) WARN_COUNT=$((WARN_COUNT + 1)) ;;
    FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
    *) die "$EXIT_USAGE" "unknown gate status: $status" ;;
  esac
}

run_cmd_gate() {
  local gate_name="$1"
  local cmd="$2"
  local pass_note="$3"
  local fail_note="$4"
  local warn_note="${5:-}"
  local tmp
  tmp="$(mktemp)"

  if (cd "$ROOT" && bash -lc "$cmd") >"$tmp" 2>&1; then
    record_result "$gate_name" "PASS" "$pass_note"
  else
    if [[ -n "$warn_note" ]]; then
      record_result "$gate_name" "WARN" "$warn_note"
    else
      record_result "$gate_name" "FAIL" "$fail_note"
    fi
  fi
  rm -f "$tmp"
}

detect_repo() {
  local remote_url
  remote_url="$(git -C "$ROOT" config --get remote.origin.url 2>/dev/null || true)"
  if [[ "$remote_url" =~ github\.com[:/]([^/]+/[^/.]+)(\.git)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi
  return 1
}

compute_scope_metrics() {
  local base_ref files loc
  if (cd "$ROOT" && git show-ref --verify --quiet refs/remotes/origin/main); then
    base_ref="$(git -C "$ROOT" merge-base HEAD origin/main)"
  elif git -C "$ROOT" rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    base_ref="HEAD~1"
  else
    base_ref=""
  fi

  if [[ -z "$base_ref" ]]; then
    printf '0 0\n'
    return 0
  fi

  files="$(git -C "$ROOT" diff --name-only "$base_ref"...HEAD | sed '/^$/d' | wc -l | tr -d ' ')"
  loc="$(git -C "$ROOT" diff --numstat "$base_ref"...HEAD | awk '{a+=$1; d+=$2} END {print a+d+0}')"
  printf '%s %s\n' "$files" "$loc"
}

write_reports() {
  local ts
  ts="$(date -Iseconds)"
  mkdir -p "$OUT_DIR"

  {
    echo "# Launch Evidence Gate Automation Report"
    echo
    echo "- Timestamp: $ts"
    echo "- Decision: **$DECISION**"
    echo "- Exit-Code: $EXIT_CODE"
    echo "- Repo: ${REPO:-unknown}"
    echo "- Rule: FAIL>0 => NO-GO, WARN>0 => WARN, else GO"
    echo
    echo "## Gate Matrix"
    echo
    echo "| Gate | Status | Note |"
    echo "|---|---|---|"
    for i in "${!GATE_NAMES[@]}"; do
      printf '| %s | %s | %s |\n' "${GATE_NAMES[$i]}" "${GATE_STATUS[$i]}" "${GATE_NOTES[$i]}"
    done
    echo
    echo "## Totals"
    echo
    echo "- PASS: $PASS_COUNT"
    echo "- WARN: $WARN_COUNT"
    echo "- FAIL: $FAIL_COUNT"
  } > "$OUT_FILE"

  local gates_tsv
  gates_tsv="$(mktemp)"
  for i in "${!GATE_NAMES[@]}"; do
    printf "%s\t%s\t%s\n" "${GATE_NAMES[$i]}" "${GATE_STATUS[$i]}" "${GATE_NOTES[$i]}" >> "$gates_tsv"
  done

  python3 - "$JSON_FILE" "$ts" "$DECISION" "$EXIT_CODE" "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT" "$gates_tsv" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
ts = sys.argv[2]
decision = sys.argv[3]
exit_code = int(sys.argv[4])
pass_count = int(sys.argv[5])
warn_count = int(sys.argv[6])
fail_count = int(sys.argv[7])
gates_path = Path(sys.argv[8])

gates = []
for line in gates_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    name, status, note = line.split("\t", 2)
    gates.append({"name": name, "status": status, "note": note})

payload = {
    "timestamp": ts,
    "decision": decision,
    "exit_code": exit_code,
    "rule": "FAIL>0 => NO-GO, WARN>0 => WARN, else GO",
    "counts": {"pass": pass_count, "warn": warn_count, "fail": fail_count},
    "gates": gates,
}
out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

  rm -f "$gates_tsv"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-healthcheck) SKIP_HEALTHCHECK=1 ;;
    --out)
      shift
      [[ $# -gt 0 ]] || die "$EXIT_USAGE" "missing value for --out"
      OUT_FILE="$1"
      ;;
    --json-out)
      shift
      [[ $# -gt 0 ]] || die "$EXIT_USAGE" "missing value for --json-out"
      JSON_FILE="$1"
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

for dep in bash git rg python3; do
  command -v "$dep" >/dev/null 2>&1 || die "$EXIT_DEPENDENCY" "required dependency missing: $dep"
done

if [[ -z "$PYTHON" ]]; then
  PYTHON="$($ROOT/scripts/dev/resolve_python.sh)"
fi
if [[ -z "$REPO" ]]; then
  REPO="$(detect_repo || true)"
fi

# Gate 1: Repo/CI
if git -C "$ROOT" rev-parse --short HEAD >/dev/null 2>&1; then
  record_result "Repo/CI" "PASS" "git HEAD resolvable"
else
  record_result "Repo/CI" "FAIL" "git HEAD unresolved"
fi

# Hard-Gate MIN_SCOPE (>=8 files OR >=230 LOC)
read -r scope_files scope_loc < <(compute_scope_metrics)
if (( scope_files >= 8 || scope_loc >= 230 )); then
  record_result "MIN_SCOPE" "PASS" "files=$scope_files loc=$scope_loc"
else
  record_result "MIN_SCOPE" "FAIL" "files=$scope_files loc=$scope_loc (need files>=8 or loc>=230; origin/main unavailable in local clone possible)"
fi

# Gate 2: Health
if [[ "$SKIP_HEALTHCHECK" -eq 1 ]]; then
  record_result "Health" "WARN" "skipped by flag"
else
  run_cmd_gate "Health" "./scripts/ops/healthcheck.sh" "healthcheck passed" "healthcheck failed"
fi

# Gate 3: Zero-CDN
run_cmd_gate "Zero-CDN" "'$PYTHON' scripts/ops/verify_guardrails.py" "guardrails passed" "guardrails failed"

# Gate 4: White-mode only
DARK_PATTERN="dark:|themeToggle|classList\\.(add|toggle)\\((\"dark\"|'dark')\\)"
if (cd "$ROOT" && rg -n "$DARK_PATTERN" app/templates app/static --glob '!app/static/vendor/**' --glob '!app/static/js/tailwindcss.min.js') >/dev/null 2>&1; then
  record_result "White-mode" "FAIL" "dark mode signatures found"
else
  record_result "White-mode" "PASS" "no dark mode signatures"
fi

# Gate 5: License
if [[ -f "$ROOT/LICENSE" || -f "$ROOT/LICENSE.md" ]]; then
  record_result "License" "PASS" "license file present"
else
  record_result "License" "FAIL" "license file missing"
fi

# Gate 6: Backup
run_cmd_gate "Backup" "'$PYTHON' -m pytest -q tests/ops/test_backup_restore_scripts.py tests/ops/test_restore_validation.py" "backup tests passed" "backup tests failed"

# Gate 7: AI
if [[ -f "$ROOT/docs/ai/AI_AGENT_OPERATING_CONTRACT.md" ]]; then
  record_result "AI" "PASS" "AI operating contract present"
else
  record_result "AI" "FAIL" "AI operating contract missing"
fi

# Hard-Gate MIN_TESTS (>=7 tests in tests/ops)
ops_test_count="$(cd "$ROOT" && rg -n '^def test_' tests/ops/*.py | wc -l | tr -d ' ')"
if (( ops_test_count >= 7 )); then
  record_result "MIN_TESTS" "PASS" "tests/ops test-count=$ops_test_count"
else
  record_result "MIN_TESTS" "FAIL" "tests/ops test-count=$ops_test_count (need >=7)"
fi

# Hard-Gate CI_GATE
run_cmd_gate "CI_GATE" "'$PYTHON' -m pytest -q tests/ops" "pytest tests/ops passed" "pytest tests/ops failed"

# Hard-Gate Evidence
if [[ "$OUT_FILE" == "$ROOT/docs/reviews/codex/LAUNCH_GATE_AUTOMATION_REPORT_20260305.md" ]]; then
  record_result "Evidence" "PASS" "evidence path matches required target"
else
  record_result "Evidence" "FAIL" "evidence path mismatch (required docs/reviews/codex/LAUNCH_GATE_AUTOMATION_REPORT_20260305.md)"
fi

if (( FAIL_COUNT > 0 )); then
  DECISION="NO-GO"
  EXIT_CODE="$EXIT_NO_GO"
elif (( WARN_COUNT > 0 )); then
  DECISION="WARN"
  EXIT_CODE="$EXIT_WARN"
else
  DECISION="GO"
  EXIT_CODE="$EXIT_GO"
fi

write_reports
printf '[launch-evidence] markdown: %s\n' "$OUT_FILE" >&2
printf '[launch-evidence] json: %s\n' "$JSON_FILE" >&2
printf '[launch-evidence] decision=%s pass=%s warn=%s fail=%s\n' "$DECISION" "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT" >&2
printf '%s\n' "$OUT_FILE"

exit "$EXIT_CODE"
