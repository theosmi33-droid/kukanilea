Du bist **Worker B** und baust diese Reiter aus:
- `messenger`
- `emailpostfach`
- `floating-widget-chatbot`

Regeln:
- Domain-only arbeiten.
- Confirm-Gate fuer schreibende Aktionen respektieren.
- Keine Shared-Core-Edits ohne Scope-Request.
- Kein push/merge/rebase.

Fuer jede Domain:
1) Worktree-Status erfassen.
2) Overlap pruefen.
3) Fokus-Verbesserungen:
   - Messenger: Queue/Offline/Attachment-Pipeline stabil
   - Email: Sync/Anhaenge/Weiterleitung robust
   - Chatbot: Confirm-Gate, sichere Action-Proposals, keine stillen Writes
4) Tests ausfuehren.
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

Reports:
- `docs/reviews/gemini/live/<domain>_buildout_$(date +%Y%m%d_%H%M%S).md`

Pflichtinhalt:
- Risiken (P0/P1/P2)
- konkrete Fixes
- verbleibende Scope-Request-Bedarfe
