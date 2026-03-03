# KUKANILEA Fleet Configuration (OpenClaw Architecture)

Das System basiert auf einer hochgradig parallelen Agenten-Flotte mit asynchronem Task-Routing.

## 1. Orchestrators (Die Dirigenten)
Zuständig für Triage, Tool-Auswahl und Context-Window-Management.
1. **Main Orchestrator**: Nimmt User-Requests entgegen, zerlegt sie in Teilaufgaben (Sub-Tasks).
2. **Review Orchestrator**: Validiert die Outputs der Worker gegen die SOUL-Directives, führt Quality Gates durch.
3. **Security Orchestrator**: Kapselt Inputs (Prompt Injection Defense), führt Red-Teaming gegen Outputs durch.

## 2. Workers (Die Spezialisten)
- W01: OCR & Vision
- W02: Document Extraction (PDF, Office)
- W03: RAG Ingestion & Embedding
- W04: RAG Retrieval (Vector + FTS)
- W05: Internet Search (Tavily/LangGraph)
- W06: Email Processing (IMAP/SMTP)
- W07: Time Tracking & Controlling
- W08: Contact Management (CRM)
- W09: ERP Sync (Lexware/KUKANILEA-Legacy)
- W10: System Maintenance & Backup
- W11: Summarization & Reporting
- W12: Code Execution & Analysis
- W13: Translation & Localization
- W14: Sentiment & Tone Analysis
- W15: Hardware I/O & Sensorik

## 3. Observer (Der Wächter)
Ein isolierter Heartbeat-Service, der System-Limits, Memory Leaks und DB-Locks überwacht. Schlägt Alarm bei Latenzen > 200ms.

## 4. Codex Cloud Rollen (verbindlich)
Diese Rollen sind fuer externe Codex-Cloud Sessions (z. B. zweiter PC) verpflichtend.

### Rolle A: `REVIEW_ONLY`
Ziel: nur auditieren, nicht editieren.

Erlaubt:
- Code lesen
- CI/Actions analysieren
- PR-Checks und Logs auswerten
- Findings mit Prioritaet (P0/P1/P2) dokumentieren

Verboten:
- Dateien aendern
- `git commit`, `git push`, `gh pr merge`
- Auto-Fixes oder Refactors

Pflichtausgabe:
- Findings zuerst (mit Datei/Zeile, Repro, Risiko)
- Dann offene Fragen/Annahmen
- Dann kurze Zusammenfassung

### Rolle B: `DEBUG_PR_ONLY`
Ziel: Bugs beheben und PR erstellen, ohne direkten Merge nach `main`.

Erlaubt:
- Editieren in Feature-Branch (`codex/debug-*`) oder Fork-Branch
- Tests lokal und in CI fixen
- PR erstellen/aktualisieren

Verboten:
- Direkter Push auf `main`
- Schutzregeln abschwaechen
- Merge ohne Maintainer-Freigabe

Pflichtablauf:
1. Repro + Root Cause
2. Minimaler Fix
3. Tests gruen (lokal + CI)
4. PR mit klarer Validation-Sektion

## 5. Remote-Scan Playbook (anderer PC)
Vor jeder Cloud-Session diesen Kontext laden:
- `docs/TAB_OWNERSHIP_RULES.md`
- `docs/SOVEREIGN_11_FINAL_PACKAGE.md`
- `docs/scope_requests/`
- `scripts/dev/check_domain_overlap.py`
- `scripts/ops/healthcheck.sh`

### Prompt-Template: Review-Only Scan
```
Mode: REVIEW_ONLY.
Arbeite read-only auf dem Repo.
Pruefe: Branch-Schutz, offene PRs, fehlerhafte/cancelled Actions, Domain-Overlap, Sovereign-11 Regeln (Zero-CDN, White-Mode, HTMX).
Liefere nur Findings (P0/P1/P2) mit Datei+Zeile, Repro und Fix-Empfehlung.
Keine Edits, keine Commits, kein Push, kein Merge.
```

### Prompt-Template: Debug+PR
```
Mode: DEBUG_PR_ONLY.
Bearbeite nur den konkreten Fehler in einem Branch codex/debug-<thema>.
Kein Push auf main, kein Merge.
Nach dem Fix: relevante Tests ausfuehren, PR erstellen, CI beobachten, Status reporten.
```

## 6. Merge-Gate (nicht verhandelbar)
- `main` bleibt protected.
- Required checks muessen gruen sein.
- Mindestens 1 Approval mit Write/Admin-Rechten.
- Kommentare muessen resolved sein.
