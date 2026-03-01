# KUKANILEA - Master-Integrationsprompt

## Geltungsbereich
Dieser Prompt steuert die Integration der Domänen 1-10 in einen stabilen Release-Stand.
Domäne 11 (Floating Widget Chatbot) ist in diesem Zyklus eingefroren und nur für Kompatibilitätschecks freigegeben.

## 1) Executive Summary
- Die 11-Domänen-Strategie hat die Entwicklung stabilisiert.
- Hauptproblem ist jetzt die Integration über Shared-Core-Dateien.
- Ziel ist eine kontrollierte Konsolidierung ohne Regressionen.

## 2) Integrationsprinzipien
- Domain-Isolation bleibt Standard.
- Shared-Core-Änderungen laufen zentral und nachvollziehbar.
- Offline-First, Auditierbarkeit und Performance-Grenzen bleiben nicht verhandelbar.

## 3) Verbindliche Regeln
- Overlap-Check vor jeder Änderung:
  `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter <domain> --files <file> --json`
- Shared-Core nur mit Freigabe:
  - `app/web.py`
  - `app/db.py`
  - `app/core/logic.py`
  - globale Layout/Auth/Policy-Dateien
- Keine direkten Commits auf `main`.
- Keine destruktiven Git-Befehle.
- Riskante Schreibaktionen nur mit Confirm-Gate + Audit-Log.

## 4) Integrationsfluss (operativ)
- Upload -> Kalender: Fristen/Termine aus Dokumenten.
- Upload -> Visualizer/Projekte: Dokumentbezug.
- Email/Messenger -> Upload: Anhangsverarbeitung.
- Email/Messenger -> Aufgaben/Kalender: Konvertierungs-Workflows.
- Aufgaben <-> Zeiterfassung: Aufwände im Workflow erfassen.
- Projekte <-> Aufgaben/Zeiten/Dokumente: Kanban als Drehscheibe.
- Einstellungen -> Alle: Rechte, Lizenz, Mesh, Branding, Backup-Policy.

## 5) Statusregel
- Domänen 1-10: aktive Integration.
- Domäne 11: keine Feature-Änderungen in diesem Lauf.

## 6) Do / Do Not
### Do
- kleine, testbare Commits
- zentrale Shared-Core-Konsolidierung
- dokumentierte Scope-Requests bei Core-Touch
- Blueprints bevorzugen statt `app/web.py` weiter aufzublähen

### Do Not
- kein Cross-Domain-Edit ohne Freigabe
- keine Secrets/harten lokalen Pfade im Code
- keine Cloud-Pflichtkomponenten für Kernflüsse

## 7) Offene Entscheidungen (zentral)
1. Shared-Core-Routing:
   - kurzfristig gezielte Änderungen in `app/web.py`
   - mittelfristig Blueprint-Migration
2. DB-Migrationen:
   - zentrales Schema, modulare Migration-Dateien
3. Tests/Docs-Allowlist:
   - pro Domäne erweitern oder zentraler Integrationspfad
4. Dirty-Worktrees:
   - revert, isolieren oder explizit freigeben

## 8) Empfohlener Ablauf
### Phase A - Scope-Freigaben (sofort)
- offene Scope-Requests pro Domäne entscheiden
- Domäne 11 weiterhin einfrieren

### Phase B - Shared-Core-Konsolidierung (1 Woche)
- Branch `codex/fix-shared-core-integration` anlegen
- erforderliche Core-Änderungen bündeln
- Konflikte auflösen und regressionsfrei testen

### Phase C - Worktree-Hygiene
- alle Worktrees auf policy-konformen Stand bringen
- Allowlist nur dort erweitern, wo fachlich begründet

### Phase D - Release-Vorbereitung
- Doku- und Testlücken schließen
- Integrations-, Last- und Endurance-Checks
- RC-Tag erstellen

## 9) Copy/Paste Prompt fuer den Integrations-Lead
```text
ROLE: Principal System Architect and Integration Lead
MAXIM: Consolidation without corruption. Integration with integrity.

MISSION:
Integrate domains 1-10 into a stable release baseline. Domain 11 is frozen for feature changes.

RULES:
- Run overlap check before edits.
- Stop on unapproved shared-core touches.
- No destructive git operations.
- No direct commits to main.

OUTPUT PER STEP:
- changed files
- overlap-check result
- tests run + result
- risks and follow-ups
```

## 10) Integration Definition of Done
- Domänen 1-10 integriert und testspezifisch grün.
- Keine offenen Overlap-Verstöße.
- Shared-Core-Änderungen dokumentiert und freigegeben.
- Offline-Degrade und Confirm-Gates verifiziert.
- Domäne 11 im Integrationslauf unverändert.
