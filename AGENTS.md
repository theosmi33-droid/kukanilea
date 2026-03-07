Du arbeitest am Produkt KUKANILEA.

Ziel:
- Nur sinnvolle, minimale, reproduzierbare Arbeit.
- Kein Scope-Drift, keine Parallel-Architektur, keine unnötigen Schließungen.

Main-Only Regel:
- `main` ist Source of Truth.
- Arbeite lokal standardmaessig nur auf `main`.
- Keine neuen Branches, außer der User verlangt es explizit.
- Vor jeder Arbeit: `git fetch origin --prune` und gegen `origin/main` prüfen.

Arbeitsmodus (genau einer pro Task):
- `Fix` oder `Harden` oder `Integrate` oder `Expand`.
- Modus nicht mischen.

Scope-Disziplin:
- Erlaube nur explizit genannte Dateien/Pfade.
- Alles andere ist verboten, solange nicht explizit freigegeben.
- Keine neuen globalen Strukturen.
- Kein Rewrite, kein Big-Bang-Refactor.

Architektur-Disziplin:
- Bestehende KUKANILEA-Architektur erweitern, nicht ersetzen.
- Keine zweite Registry/Router/MIA-Schicht.
- Guardrails, Confirm-Gates und Audit fail-closed beibehalten.

Pflichtvalidierung (bei Codeaenderungen):
1) `python scripts/ops/verify_guardrails.py`
2) `bash scripts/ops/healthcheck.sh --strict-doctor --skip-pytest`
3) Nur relevante `pytest`-Tests fuer den Scope

Definition of Done:
- Root Cause identifiziert.
- Kleinster sicherer Patch umgesetzt.
- Relevante Checks gruen.
- Keine unbeabsichtigten Nebenwirkungen außerhalb Scope.

Ausgabeformat:
1. Analyse (Fehler + Root Cause + Prioritaet)
2. Aenderungen (Dateien + was + warum)
3. Validierung (Befehle + Ergebnisse)
4. Restrisiken
5. Abschluss (PR-ready ja/nein)
