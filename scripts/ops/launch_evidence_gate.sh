#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -z "${PYTHON:-}" ]]; then
  for candidate in \
    ".venv/bin/python" \
    "$HOME/.pyenv/versions/3.12.12/bin/python" \
    "$HOME/.pyenv/versions/3.11.14/bin/python" \
    "python3"; do
    if [[ "$candidate" == "python3" ]]; then
      if command -v python3 >/dev/null 2>&1 && python3 -V >/dev/null 2>&1; then
        PYTHON="python3"
        break
      fi
    elif [[ -x "$candidate" ]] && "$candidate" -V >/dev/null 2>&1; then
      PYTHON="$candidate"
      break
    fi
  done
fi
: "${PYTHON:?No usable Python runtime found. Set PYTHON=/path/to/python}"

OUT_DIR="docs/reviews/codex"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$OUT_DIR/LAUNCH_EVIDENCE_RUN_${STAMP}.md"
mkdir -p "$OUT_DIR"

PASS=0
WARN=0
FAIL=0

write_header() {
  cat > "$OUT" <<MD
# Launch Evidence Run ($STAMP)

- Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
- Branch: $(git rev-parse --abbrev-ref HEAD)
- Commit: $(git rev-parse HEAD)
- Python: $PYTHON

| Gate | Status | Details |
|---|---|---|
MD
}

record() {
  local gate="$1"
  local status="$2"
  local details="$3"
  printf '| %s | %s | %s |\n' "$gate" "$status" "$details" >> "$OUT"
  case "$status" in
    PASS) PASS=$((PASS + 1)) ;;
    WARN) WARN=$((WARN + 1)) ;;
    FAIL) FAIL=$((FAIL + 1)) ;;
  esac
}

write_header

if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    prs="$(gh pr list --limit 20 --json number,state,title --jq 'length' 2>/dev/null || echo '?')"
    failing_completed_runs="$(gh run list --limit 20 --json status,conclusion --jq '[.[] | select(.status=="completed" and .conclusion!="success")] | length' 2>/dev/null || echo '?')"
    if [[ "$failing_completed_runs" == "0" ]]; then
      record "Gate 1 (Repo+CI)" "PASS" "gh verfügbar; offene PRs (Top20): $prs; failing completed runs (Top20): 0"
    else
      record "Gate 1 (Repo+CI)" "WARN" "gh verfügbar; failing completed runs (Top20): $failing_completed_runs"
    fi
  else
    record "Gate 1 (Repo+CI)" "WARN" "gh vorhanden, aber nicht authentifiziert"
  fi
else
  record "Gate 1 (Repo+CI)" "WARN" "gh CLI nicht verfügbar"
fi

if "$ROOT_DIR/scripts/ops/healthcheck.sh" >/tmp/kukanilea_launch_healthcheck.log 2>&1; then
  record "Gate 2 (Core+Healthcheck)" "PASS" "healthcheck.sh erfolgreich"
else
  tail_msg="$(tail -n 3 /tmp/kukanilea_launch_healthcheck.log | tr '\n' ' ' | sed 's/|/\\|/g')"
  record "Gate 2 (Core+Healthcheck)" "FAIL" "healthcheck.sh fehlgeschlagen: ${tail_msg}"
fi

ext_hits="$(rg -n "https?://" app/templates app/static 2>/dev/null | grep -v "w3.org" || true)"
if [[ -z "$ext_hits" ]]; then
  record "Gate 3 (Zero-CDN Scan)" "PASS" "Kein externer URL-Fund in app/templates + app/static"
else
  count="$(printf '%s\n' "$ext_hits" | wc -l | tr -d ' ')"
  record "Gate 3 (Zero-CDN Scan)" "FAIL" "$count Treffer für externe URLs"
fi

if rg -n "prefers-color-scheme\s*:\s*dark|data-theme=\"dark\"|theme-dark|--color-dark|\.dark\b" app/static/css app/templates >/tmp/kukanilea_darkmode_hits.log 2>&1; then
  count="$(wc -l < /tmp/kukanilea_darkmode_hits.log | tr -d ' ')"
  record "Gate 4 (White-Mode)" "FAIL" "Dark-Mode-Reste gefunden ($count Treffer)"
else
  record "Gate 4 (White-Mode)" "PASS" "Keine Dark-Mode-Reste im produktiven CSS/Template-Set"
fi

if [[ -f scripts/ops/generate_enterprise_license.py ]]; then
  record "Gate 5 (Lizenz)" "WARN" "Skript-Präsenz geprüft; SMB/Excel Sperrfall muss manuell E2E validiert werden"
else
  record "Gate 5 (Lizenz)" "WARN" "Kein Lizenz-Check-Skript gefunden"
fi

if [[ -x scripts/ops/backup_to_nas.sh && -x scripts/ops/restore_from_nas.sh ]]; then
  record "Gate 6 (Backup/Restore)" "PASS" "backup_to_nas.sh + restore_from_nas.sh vorhanden"
else
  record "Gate 6 (Backup/Restore)" "FAIL" "Backup-/Restore-Skripte unvollständig"
fi

if [[ -f scripts/ops/toggle_ai_mode.py ]]; then
  record "Gate 7 (Local AI)" "WARN" "AI toggle vorhanden; Modell-/Guardrail-E2E separat prüfen"
else
  record "Gate 7 (Local AI)" "WARN" "Kein AI-Toggle-Skript gefunden"
fi

if "$PYTHON" scripts/ops/verify_guardrails.py >/tmp/kukanilea_guardrails.log 2>&1; then
  record "Gate 8 (Guardrails)" "PASS" "verify_guardrails.py erfolgreich"
else
  tail_msg="$(tail -n 3 /tmp/kukanilea_guardrails.log | tr '\n' ' ' | sed 's/|/\\|/g')"
  record "Gate 8 (Guardrails)" "FAIL" "verify_guardrails.py fehlgeschlagen: ${tail_msg}"
fi

{
  echo
  echo "## Summary"
  echo
  echo "- PASS: $PASS"
  echo "- WARN: $WARN"
  echo "- FAIL: $FAIL"
  if [[ "$FAIL" -eq 0 ]]; then
    echo "- Launch-Gate: **GO**"
  else
    echo "- Launch-Gate: **NO-GO**"
  fi
} >> "$OUT"

echo "$OUT"
[[ "$FAIL" -eq 0 ]]
