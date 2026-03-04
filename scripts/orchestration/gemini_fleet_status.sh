#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
RUN_ID="${1:-}"

if [[ -z "$RUN_ID" ]]; then
  echo "usage: $0 <run_id>"
  exit 2
fi

RUN_DIR="$ROOT/data/gemini_fleet_runs/$RUN_ID"
if [[ ! -d "$RUN_DIR" ]]; then
  echo "run directory not found: $RUN_DIR"
  exit 2
fi

echo "=== Gemini Fleet Status: $RUN_ID ==="
pid_count=0
for pid_file in "$RUN_DIR"/*.pid; do
  [[ -f "$pid_file" ]] || continue
  pid_count=$((pid_count + 1))
  domain="$(basename "$pid_file" .pid)"
  pid="$(cat "$pid_file")"
  log="$RUN_DIR/$domain.log"
  raw_log="$RUN_DIR/$domain.raw.log"
  if kill -0 "$pid" 2>/dev/null; then
    state="RUNNING"
  else
    state="DONE"
  fi
  echo "[$state] $domain pid=$pid"
  if [[ -f "$log" ]]; then
    tail -n 2 "$log" | sed 's/^/  log: /'
  fi
  if [[ -f "$raw_log" ]]; then
    tail -n 1 "$raw_log" | sed 's/^/  raw: /'
  fi
done

if [[ "$pid_count" -eq 0 ]]; then
  echo "[info] no pid files found (serial run or already cleaned up)"
  for log in "$RUN_DIR"/*.log; do
    [[ -f "$log" ]] || continue
    domain="$(basename "$log" .log)"
    echo "[SERIAL] $domain"
    tail -n 2 "$log" | sed 's/^/  log: /'
  done
fi

echo
echo "Reports:"
for domain in dashboard upload emailpostfach messenger kalender aufgaben zeiterfassung projekte excel-docs-visualizer einstellungen floating-widget-chatbot; do
  report_glob="/Users/gensuminguyen/Kukanilea/worktrees/$domain/docs/reviews/${domain}_kickoff_${RUN_ID}.md"
  if [[ -f "$report_glob" ]]; then
    echo "  [OK] $report_glob"
  else
    echo "  [..] $report_glob"
  fi
done

echo
echo "Shared memory snapshot:"
"$CORE/.build_venv/bin/python" "$CORE/scripts/shared_memory.py" --db "$ROOT/data/agent_orchestra_shared.db" read | sed -n '1,120p'
