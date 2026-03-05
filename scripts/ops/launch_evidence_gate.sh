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

die() { local code="$1"; shift; printf '[launch-evidence] ERROR: %s\n' "$*" >&2; exit "$code"; }

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
  local name="$1" status="$2" note="$3"
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
  local gate_name="$1" cmd="$2" pass_note="$3" fail_note="$4"
  if (cd "$ROOT" && bash -lc "$cmd") >/dev/null 2>&1; then
    record_result "$gate_name" "PASS" "$pass_note"
  else
    record_result "$gate_name" "FAIL" "$fail_note"
  fi
}

detect_repo() {
  local remote_url
  remote_url="$(git -C "$ROOT" config --get remote.origin.url 2>/dev/null || true)"
  if [[ "$remote_url" =~ github\.com[:/]([^/]+/[^/.]+)(\.git)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
  fi
}

compute_scope_metrics() {
  local base_ref files loc
  if (cd "$ROOT" && git show-ref --verify --quiet refs/remotes/origin/main); then
    base_ref="$(git -C "$ROOT" merge-base HEAD origin/main)"
  elif git -C "$ROOT" rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    base_ref="HEAD~1"
  else
    printf '0 0\n'
    return 0
  fi
  files="$(git -C "$ROOT" diff --name-only "$base_ref"...HEAD | sed '/^$/d' | wc -l | tr -d ' ')"
  loc="$(git -C "$ROOT" diff --numstat "$base_ref"...HEAD | awk '{a+=$1; d+=$2} END {print a+d+0}')"
  printf '%s %s\n' "$files" "$loc"
}

write_reports() {
  local ts; ts="$(date -Iseconds)"
  mkdir -p "$OUT_DIR"
  {
    echo "# Launch Evidence Gate Automation Report"
    echo
    echo "- Timestamp: $ts"
    echo "- Decision: **$DECISION**"
    echo "- Exit-Code: $EXIT_CODE"
    echo "- Repo: ${REPO:-unknown}"
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

  python3 - "$JSON_FILE" "$ts" "$DECISION" "$EXIT_CODE" "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT" \
    "$(printf '%s\n' "${GATE_NAMES[@]}")" \
    "$(printf '%s\n' "${GATE_STATUS[@]}")" \
    "$(printf '%s\n' "${GATE_NOTES[@]}")" <<'PY'
import json, sys
out, ts, decision, exit_code, p, w, f, gate_names, gate_status, gate_notes = sys.argv[1:11]
Path = __import__("pathlib").Path
names = gate_names.splitlines()
statuses = gate_status.splitlines()
notes = gate_notes.splitlines()
gates = [
  {"name": names[i], "status": statuses[i], "note": notes[i]}
  for i in range(min(len(names), len(statuses), len(notes)))
]
Path(out).write_text(json.dumps({
  "timestamp": ts,
  "decision": decision,
  "exit_code": int(exit_code),
  "counts": {"pass": int(p), "warn": int(w), "fail": int(f)},
  "gates": gates,
}, indent=2) + "\n", encoding="utf-8")
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-healthcheck) SKIP_HEALTHCHECK=1 ;;
    --out) shift; OUT_FILE="$1" ;;
    --json-out) shift; JSON_FILE="$1" ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; die "$EXIT_USAGE" "unknown argument: $1" ;;
  esac
  shift
done

for dep in bash git rg python3; do
  command -v "$dep" >/dev/null 2>&1 || die "$EXIT_DEPENDENCY" "required dependency missing: $dep"
done
[[ -n "$PYTHON" ]] || PYTHON="$($ROOT/scripts/dev/resolve_python.sh)"
[[ -n "$REPO" ]] || REPO="$(detect_repo || true)"

# Repo/CI
if git -C "$ROOT" rev-parse --short HEAD >/dev/null 2>&1; then
  record_result "Repo/CI" "PASS" "git HEAD resolvable"
else
  record_result "Repo/CI" "FAIL" "git HEAD unresolved"
fi

read -r scope_files scope_loc < <(compute_scope_metrics)
if (( scope_files >= 8 || scope_loc >= 230 )); then
  record_result "MIN_SCOPE" "PASS" "files=$scope_files loc=$scope_loc"
else
  record_result "MIN_SCOPE" "FAIL" "files=$scope_files loc=$scope_loc (need files>=8 or loc>=230; origin/main unavailable in local clone possible)"
fi

if [[ "$SKIP_HEALTHCHECK" -eq 1 ]]; then
  record_result "Health" "WARN" "skipped by flag"
else
  run_cmd_gate "Health" "./scripts/ops/healthcheck.sh" "healthcheck passed" "healthcheck failed"
fi

run_cmd_gate "Zero-CDN" "'$PYTHON' scripts/ops/verify_guardrails.py" "guardrails passed" "guardrails failed"

DARK_PATTERN="dark:|themeToggle|classList\\.(add|toggle)\\((\"dark\"|'dark')\\)"
if (cd "$ROOT" && rg -n "$DARK_PATTERN" app/templates app/static --glob '!app/static/vendor/**' --glob '!app/static/js/tailwindcss.min.js') >/dev/null 2>&1; then
  record_result "White-mode" "FAIL" "dark mode signatures found"
else
  record_result "White-mode" "PASS" "no dark mode signatures"
fi

# License
LICENSE_FILE="${LICENSE_FILE:-$ROOT/instance/license.json}"
LICENSE_PUBKEY_ENV="${LICENSE_PUBKEY_ENV:-LICENSE_PUBLIC_KEY_HEX}"
license_status="$(cd "$ROOT" && "$PYTHON" - "$LICENSE_FILE" "$LICENSE_PUBKEY_ENV" <<'PY'
import sys
from app.core.license_checker import check_license_file
license_file, pub_env = sys.argv[1:3]
try:
    payload = check_license_file(license_file, pub_env)
except Exception as exc:
    print(f"ERROR:{exc}")
    raise SystemExit(2)
print(f"{payload.get('status','LOCKED')}:{payload.get('reason','unknown')}")
raise SystemExit(0)
PY
)" || true
if [[ "$license_status" == OK:* ]]; then
  record_result "License" "PASS" "status=$license_status"
elif [[ "$license_status" == WARN:* ]]; then
  record_result "License" "WARN" "status=$license_status"
else
  record_result "License" "FAIL" "status=${license_status:-LOCKED:unknown}"
fi

# Backup / restore evidence drill
BACKUP_REPORT="${BACKUP_REPORT:-$ROOT/instance/evidence_backup_report.txt}"
RESTORE_REPORT="${RESTORE_REPORT:-$ROOT/instance/evidence_restore_report.txt}"
if (cd "$ROOT" && TENANT_ID="${TENANT_ID:-DEMO_TENANT}" REPORT_FILE="$BACKUP_REPORT" bash scripts/ops/backup_to_nas.sh && TENANT_ID="${TENANT_ID:-DEMO_TENANT}" REPORT_FILE="$RESTORE_REPORT" EXPECTED_RESTORE_DIRS="${EXPECTED_RESTORE_DIRS:-}" bash scripts/ops/restore_from_nas.sh); then
  if (cd "$ROOT" && rg -q '^checksum_sha256=' "$BACKUP_REPORT" && rg -q '^backup_size_bytes=' "$BACKUP_REPORT" && rg -q '^target_path=' "$BACKUP_REPORT" && rg -q '^verify_db=ok' "$RESTORE_REPORT" && rg -q '^verify_files=ok' "$RESTORE_REPORT" && rg -q '^restore_validation=ok' "$RESTORE_REPORT"); then
    record_result "Backup" "PASS" "backup/restore evidence verified"
  else
    record_result "Backup" "FAIL" "backup/restore reports missing required evidence"
  fi
else
  record_result "Backup" "FAIL" "backup/restore drill execution failed"
fi

if [[ -f "$ROOT/docs/ai/AI_AGENT_OPERATING_CONTRACT.md" ]]; then
  record_result "AI" "PASS" "AI operating contract present"
else
  record_result "AI" "FAIL" "AI operating contract missing"
fi

ops_test_count="$(cd "$ROOT" && rg -n '^def test_' tests/ops/*.py | wc -l | tr -d ' ')"
if (( ops_test_count >= 7 )); then
  record_result "MIN_TESTS" "PASS" "tests/ops test-count=$ops_test_count"
else
  record_result "MIN_TESTS" "FAIL" "tests/ops test-count=$ops_test_count (need >=7)"
fi

run_cmd_gate "CI_GATE" "'$PYTHON' -m pytest -q tests/ops" "pytest tests/ops passed" "pytest tests/ops failed"

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
printf '%s\n' "$OUT_FILE"
exit "$EXIT_CODE"
