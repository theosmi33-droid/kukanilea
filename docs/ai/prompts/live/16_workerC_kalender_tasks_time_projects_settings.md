Du bist **Worker C** und baust diese Reiter aus:
- `kalender`
- `aufgaben`
- `zeiterfassung`
- `projekte`
- `einstellungen`

Regeln:
- Nur domain-owned Dateien.
- Projekte vs Aufgaben trennen (keine Funktionsduplikate).
- Keine Shared-Core-Dateien direkt aendern.
- Kein push/merge/rebase.

Fuer jede Domain:
1) Status erfassen + Overlap pruefen
2) Sicheren Ausbau umsetzen
3) Tests laufen lassen
4) Report erstellen

Fokus je Domain:
- kalender: ICS/Reminder/Deadline-Extraction
- aufgaben: Statusflow + Delegation + Benachrichtigungen
- zeiterfassung: Timer-Stabilitaet + Export
- projekte: Kanban-Moves + Activity-Log
- einstellungen: RBAC + Confirm-Gates + Lizenz/Backup/Mesh

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
- Findings P0/P1/P2
- durchgefuehrte Fixes
- offene Blocker inkl. reproduzierbarer Schritte
