#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
OUT_DIR="$CORE/docs/reviews/codex"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$OUT_DIR/OVERLAP_MATRIX_11_${STAMP}.md"

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

mkdir -p "$OUT_DIR"

# Range mode:
# - ancestry (default): compare branch-owned commits since merge-base (`git diff main...HEAD`)
# - content: compare current worktree content against main (`git diff main`)
RANGE_MODE="${OVERLAP_RANGE_MODE:-ancestry}"
if [[ "$RANGE_MODE" == "content" ]]; then
  DIFF_RANGE="main"
else
  DIFF_RANGE="main...HEAD"
fi

{
  echo "# Overlap Matrix 11 Domains"
  echo
  echo "_Range mode: ${RANGE_MODE} (${DIFF_RANGE})_"
  echo
  echo "| Domain | Branch | Dirty | Diff vs main | Overlap |"
  echo "|---|---|---:|---:|---|"
} > "$OUT"

for d in "${DOMAINS[@]}"; do
  WT="$ROOT/worktrees/$d"
  if [[ ! -d "$WT" ]]; then
    echo "| $d | missing | - | - | MISSING_WORKTREE |" >> "$OUT"
    continue
  fi

  cd "$WT"
  branch="$(git branch --show-current || echo '?')"
  dirty="$(git status --porcelain | wc -l | tr -d ' ')"
  diff_count="$(git diff --name-only "$DIFF_RANGE" | wc -l | tr -d ' ')"

  overlap="OK"
  if [[ "$diff_count" != "0" ]]; then
    files=()
    while IFS= read -r f; do
      files+=("$f")
    done < <(git diff --name-only "$DIFF_RANGE")
    json="$(python "$CORE/scripts/dev/check_domain_overlap.py" --reiter "$d" --files "${files[@]}" --json 2>/dev/null || true)"
    overlap="$(python - <<'PY' "$json"
import json,sys
raw=sys.argv[1].strip()
if not raw:
    print("ERROR")
    raise SystemExit(0)
try:
    data=json.loads(raw)
    print(data.get("status","UNKNOWN"))
except Exception:
    print("ERROR")
PY
)"
  else
    overlap="OK(no_diff)"
  fi

  echo "| $d | $branch | $dirty | $diff_count | $overlap |" >> "$OUT"
done

echo "$OUT"
