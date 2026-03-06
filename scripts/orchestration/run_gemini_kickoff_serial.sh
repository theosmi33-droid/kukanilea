#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
WORKTREES="$ROOT/worktrees"
DB="$ROOT/data/agent_orchestra_shared.db"
PY="$CORE/.build_venv/bin/python"
# Ensure Homebrew binaries are reachable in non-login shells (nohup/cron).
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
STAMP="${1:-$(date +%Y%m%d_%H%M%S)}"
RUN_DIR="$ROOT/data/gemini_fleet_runs/$STAMP"
FLEET_APPROVAL_MODE="${GEMINI_FLEET_APPROVAL_MODE:-default}"
if [[ "$FLEET_APPROVAL_MODE" != "default" && "$FLEET_APPROVAL_MODE" != "yolo" ]]; then
  echo "invalid GEMINI_FLEET_APPROVAL_MODE=$FLEET_APPROVAL_MODE (expected: default|yolo)" >&2
  exit 2
fi
if [[ "$FLEET_APPROVAL_MODE" == "yolo" ]]; then
  echo "[warn] GEMINI_FLEET_APPROVAL_MODE=yolo enables unsafe autonomous actions" >&2
fi

DOMAINS=(
  dashboard
  upload
  emailpostfach
  messenger
  kalender
  aufgaben
  zeiterfassung
  projekte
  excel-docs-visualizer
  einstellungen
  floating-widget-chatbot
)

mkdir -p "$RUN_DIR"

# Ensure GitHub token env is available for Gemini MCP in non-login shells.
if command -v gh >/dev/null 2>&1; then
  GH_AUTH_TOKEN="$(gh auth token 2>/dev/null || true)"
  GH_AUTH_TOKEN="$(printf '%s' "$GH_AUTH_TOKEN" | sed -E 's/^[[:space:]]*Bearer[[:space:]]+//')"
  if [[ -n "$GH_AUTH_TOKEN" ]]; then
    export GITHUB_MCP_PAT="${GITHUB_MCP_PAT:-$GH_AUTH_TOKEN}"
    export GITHUB_TOKEN="${GITHUB_TOKEN:-$GH_AUTH_TOKEN}"
    export GH_TOKEN="${GH_TOKEN:-$GH_AUTH_TOKEN}"
  fi
  unset GH_AUTH_TOKEN
fi

"$PY" "$CORE/scripts/shared_memory.py" --db "$DB" init >/dev/null
"$PY" "$CORE/scripts/shared_memory.py" --db "$DB" set-context \
  --key "fleet_run_$STAMP" \
  --value "gemini_cli_serial_kickoff_started" \
  --actor "codex" \
  --source "scripts/orchestration/run_gemini_kickoff_serial.sh" >/dev/null

for domain in "${DOMAINS[@]}"; do
  wt="$WORKTREES/$domain"
  log="$RUN_DIR/${domain}.log"
  report_rel="docs/reviews/${domain}_kickoff_${STAMP}.md"
  report_abs="$wt/$report_rel"
  prompt_file="$RUN_DIR/${domain}.prompt.txt"

  mkdir -p "$wt/docs/reviews"

  "$PY" "$CORE/scripts/shared_memory.py" --db "$DB" upsert-domain \
    --domain "$domain" \
    --action "kickoff_started" \
    --commit "" \
    --status "IN_PROGRESS" \
    --actor "codex" \
    --source "gemini_fleet_serial" >/dev/null

  cat >"$prompt_file" <<EOF
Du arbeitest als Domain-Agent fuer "$domain" im Worktree "$wt".

Harte Regeln:
- Kein git push, kein merge, kein rebase.
- Keine Aenderungen an shared-core Dateien (z.B. app/web.py, app/db.py, app/templates/layout.html), ausser nur dokumentierte Empfehlung.
- Erzeuge in diesem Lauf KEINE grossen Refactors.

Ziele dieses Kickoff-Laufs:
1. Analysiere den Domain-Stand (git status, relevante Domain-Dateien, Domain-Tests).
2. Pruefe Zero-CDN/White-Mode/HTMX-Compliance nur fuer Domain-sichtbare Teile.
3. Fuehre einen Domain-Overlap-Check nur fuer aktuell geaenderte Dateien aus (falls keine geaenderten Dateien: notiere "no local diff").
4. Erstelle einen konkreten Arbeitsplan mit P0/P1/P2 in Markdown.
5. Schreibe den Bericht in sauberem Markdown.

Berichtsformat:
- Titel: "Kickoff Report $domain"
- Abschnitt "Current State"
- Abschnitt "Findings (P0/P1/P2)"
- Abschnitt "First 3 Safe Commits"
- Abschnitt "Open Questions"

Zum Schluss:
- Gib eine kurze Text-Zusammenfassung aus (max 12 Zeilen).
EOF

  echo "=== domain=$domain ===" >"$log"
  "$PY" "$CORE/scripts/ai/gemini_cli.py" \
    --domain "$domain" \
    --prompt-file "$prompt_file" \
    --cwd "$wt" \
    --output "$report_abs" \
    --log "$log" \
    --timeout-seconds 900 \
    --approval-mode "$FLEET_APPROVAL_MODE" || true

  status="DONE"
  if [[ ! -s "$report_abs" ]]; then
    status="FAILED"
  fi

  "$PY" "$CORE/scripts/shared_memory.py" --db "$DB" upsert-domain \
    --domain "$domain" \
    --action "kickoff_finished" \
    --commit "" \
    --status "$status" \
    --actor "codex" \
    --source "gemini_fleet_serial" >/dev/null

  echo "domain=$domain status=$status report=$report_abs"
done

echo "run_dir=$RUN_DIR"
echo "approval_mode=$FLEET_APPROVAL_MODE"
echo "db=$DB"
echo "status_cmd=$CORE/scripts/orchestration/gemini_fleet_status.sh $STAMP"
