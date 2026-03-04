# KUKANILEA Finalization Checklist (15-Minuten Morning Run)

**Datum:** 2026-03-04  
**Ziel:** In <15 Minuten feststellen, ob `main` releasefähig ist.

## 1. Repo Sync (2 Min)
```bash
cd /Users/gensuminguyen/Kukanilea/kukanilea_production
git status --short
git fetch origin --prune
git rev-parse --short HEAD
git rev-parse --short origin/main
```

**PASS wenn:** `HEAD == origin/main` (oder bewusst dokumentierter lokaler Stand).

## 2. CI/PR Gate (2 Min)
```bash
gh pr list --repo theosmi33-droid/kukanilea --state open
gh run list --repo theosmi33-droid/kukanilea --limit 8
```

**PASS wenn:**
- Keine offenen blockierenden PRs
- Letzte `main` Workflows: `completed/success`

## 3. Guardrails (2 Min)
```bash
bash scripts/dev/vscode_guardrails.sh --check
bash scripts/orchestration/overlap_matrix_11.sh
```

**PASS wenn:**
- `vscode-configs: OK`
- Neue Overlap-Matrix ohne P0-Blocker

## 4. Healthcheck + Tests (5 Min)
```bash
./scripts/ops/healthcheck.sh
pytest -q
```

**PASS wenn:**
- Healthcheck vollständig grün
- Keine neuen Test-Failures

## 5. Worktree Hygiene (2 Min)
```bash
ROOT=/Users/gensuminguyen/Kukanilea
for d in dashboard upload emailpostfach messenger kalender aufgaben zeiterfassung projekte excel-docs-visualizer einstellungen floating-widget-chatbot; do
  cd "$ROOT/worktrees/$d"
  echo "=== $d ==="
  echo "branch=$(git branch --show-current)"
  echo -n "ahead_behind=" && git rev-list --left-right --count origin/main...HEAD
  echo -n "dirty=" && git status --porcelain | wc -l
  echo
done
```

**PASS wenn:**
- Keine unerwarteten dirty states
- Branches konsistent (bewusste Abweichungen dokumentiert)

## 6. Release Decision (1 Min)

Setze den Tagesstatus in den Report:
- `GO`: alle 5 Gates grün
- `GO with Notes`: keine P0, nur bekannte P1/P2
- `NO-GO`: ein Gate rot oder CI/Healthcheck instabil

Empfohlener Ablagepfad für Tagesreport:
`docs/reviews/codex/FINAL_DECISION_<YYYYMMDD_HHMM>.md`

---

## Optional: Prozesse sauber beenden nach Session
```bash
pkill -f '/opt/homebrew/bin/Gemini' || true
pkill -f 'gemini-cli-security' || true
pkill -f 'gemini-cli-jules' || true
```

## Optional: Prozesse neu starten (4 Worker-Fenster)
```bash
gemini
gemini
gemini
gemini
```

