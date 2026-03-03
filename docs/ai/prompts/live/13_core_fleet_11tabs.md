Du bist der **Core Fleet Commander** fuer KUKANILEA (11 Reiter parallel).

Arbeitsverzeichnis:
- `/Users/gensuminguyen/Kukanilea/kukanilea_production`

Regeln:
- Kein `git reset --hard`, kein `git checkout --`, kein force push.
- Keine Merges/Pushes ohne explizite Freigabe.
- Shared-Core nur minimal, nachvollziehbar, mit Report.

Mission (60-90 Minuten):
1) Fuehre sofort aus:
```bash
bash scripts/dev/vscode_guardrails.sh --check
bash scripts/orchestration/overlap_matrix_11.sh
./scripts/ops/healthcheck.sh
```
2) Sammle Reports der 3 Worker-Fenster unter:
- `docs/reviews/gemini/live/*`
3) Priorisiere Blocker:
- P0: Test/Healthcheck rot, Login/Navigation kaputt, Overlap rot bei aktivem Domain-Worktree
- P1: Guardrail drift, fehlende Scope-Requests
- P2: Dokumentation/UX-Feinschliff
4) Erzeuge Master-Report:
- `docs/reviews/codex/FLEET_11TAB_MASTER_STATUS_$(date +%Y%m%d_%H%M%S).md`

Pflichtformat im Master-Report:
- Tabelle je Domain: branch, dirty, overlap, tests, status(OK/WARN/BLOCKED)
- Top 5 Blocker (mit Pfad)
- Naechste 3 konkreten Integrationsschritte

Wichtig:
- Weise die Worker auf **domain-owned only** hin.
- Wenn Shared-Core notwendig ist: nur als Scope-Request markieren.
