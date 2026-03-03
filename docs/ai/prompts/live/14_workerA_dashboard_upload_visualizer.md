Du bist **Worker A** und baust diese Reiter aus:
- `dashboard`
- `upload`
- `excel-docs-visualizer`

Regeln:
- Nur domain-owned Dateien aendern.
- Keine Shared-Core-Dateien direkt anpassen.
- Kein push/merge/rebase.

Fuer jede Domain exakt dieser Ablauf:
1) In Worktree wechseln.
2) Status + Overlap pruefen.
3) Kleine, sichere Verbesserungen umsetzen (Sovereign-11 konform: Zero-CDN, White-Mode, HTMX-vertraeglich).
4) Relevante Tests laufen lassen.
5) Report schreiben.

Commands pro Domain (Template):
```bash
cd /Users/gensuminguyen/Kukanilea/worktrees/<domain>
git status --porcelain
FILES=$(git diff --name-only main)
if [ -n "$FILES" ]; then
  python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter <domain> --files $FILES --json
else
  echo '{"status":"OK","reason":"no_diff"}'
fi
pytest -q || true
```

Report pro Domain:
- `docs/reviews/gemini/live/<domain>_buildout_$(date +%Y%m%d_%H%M%S).md`

Report-Inhalt:
- Current state
- Findings P0/P1/P2
- Umgesetzte sichere Verbesserungen
- Offene Punkte fuer Core/Scope-Request
