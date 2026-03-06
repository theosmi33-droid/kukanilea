# Integrations-Readout (Basis: lokaler `work`-Stand)

## Vorbemerkung zur Basis
- Im aktuellen Clone ist **kein `origin` Remote konfiguriert** (`git remote -v` leer).
- Damit konnte `origin/main` nicht direkt gefetched oder gegen lokale Branches verglichen werden.
- Evidenzbasis in diesem Readout ist daher: lokaler `work`-Branch + vorhandene Integrations-Commits im lokalen Verlauf.

## 1) Bereits kompatible Arbeitspakete (evidence-basiert)

### A) Flow Framework + Approval Engine
- `CrossToolFlowEngine` erzwingt Confirm-Gates bei Write-Schritten (`step.writes_state` + fehlende Confirmation -> `confirm_required`).
- Bei ungesunden Tools wird deterministisch degradiert (`flow.fallback_applied`) statt blind weiterzuschreiben.
- Prompt-Injection wird vor Textübernahme neutralisiert/abgeblockt.

Bewertung: **kompatibel** mit den kanonischen Regeln (confirm-before-write, deterministic fallback, auditierbare Ereignisse).

### B) Router/Registry (kanonische Action-IDs)
- Router nutzt keine harte Legacy-Matrix mehr, sondern `ActionRegistry` via `create_action_registry()`.
- Action-IDs folgen kanonischem Schema `domain.entity.verb[.modifier...]`.
- Registry-Validierung erzwingt für Write-Actions `confirm_required=True` und `audit_required=True`.

Bewertung: **kompatibel** mit kanonischen Regeln (ID-Kanon, policy-first Routing, Write-Guards).

### C) Audit Schema
- Stabiler MIA-Eventkatalog in `app/mia_audit.py` (`MIA_EVENTS_STABLE`).
- Event-Emission lehnt unbekannte Eventtypen ab.
- Payload-Sanitization redaktiert Secret-Felder deterministisch.

Bewertung: **kompatibel** mit kanonischen Regeln (stabile Eventtypen, auditierbare + sanitizte Payloads).

### D) Launch Gates (ops)
- Gate-7 Smoke (`scripts/ops/gate7_evidence.py`) ist in `launch_evidence_gate.sh` integriert.
- Required-Artifacts werden auf definierte Check-Namen geprüft.

Bewertung: **kompatibel** mit Gate-Härtung (evidence-driven).

## 2) Konfliktrisiken nach Fokusbereichen

### Shared services
- **Risiko: mittel**.
- Grund: `scripts/ops/launch_evidence_gate.sh` wurde in mehreren Integrationspaketen erweitert (u.a. MIA-Audit und Gate-7). Sequenzielle Erweiterungen sind kompatibel, aber bei parallelem Rebase hoch konfliktanfällig wegen langem Shell-Skript mit vielen Gate-Blöcken.

### router/registry
- **Risiko: mittel bis hoch**.
- Grund: `manager_agent.py` wurde zuerst für sicheren Router angepasst und später erneut auf deklarative Registry umgebaut. Diese Datei ist Integrations-Hotspot (Intent-Mapping, Confirm-Mode, Offline-Block).

### audit schema
- **Risiko: niedrig bis mittel**.
- Grund: stabiler Eventkatalog ist eingeführt; Konflikte entstehen primär, wenn neue Eventnamen ohne Aufnahme in `MIA_EVENTS_STABLE` kommen.

### approval engine
- **Risiko: mittel**.
- Grund: Approval-Logik ist an mehreren Ebenen vorhanden (Flow-Step-Confirm, Router-Confirm-Mode, Intake-Confirm-Pfade). Semantik ist aktuell konsistent, aber drift-gefährdet bei unabhängigen Änderungen.

### flow framework
- **Risiko: mittel**.
- Grund: Framework ist deterministisch, aber stark gekoppelt an Action-Namen + Kontextfelder. Neue Flows ohne Registry-/Schema-Abgleich erzeugen Integrationsbrüche statt stiller Fehler (gewollt, aber merge-sensitiv).

## 3) Zusammengeführt wurde nur Kanonisches
- Dieser Integrationsschritt hat **keine neue fachliche Zusammenführung** von divergenten Regeln vorgenommen.
- Es wurde nur ein Test-Drift behoben, um die bestehende kanonische Semantik abzubilden:
  - `release_conductor_preflight.sh` liefert bei optionalen `gh/prod` Warnungen weiterhin Exit 0 (sofern Guard/Test nicht FAIL).
  - Testerwartung in `tests/test_release_conductor_preflight.py` wurde entsprechend korrigiert.

## 4) Verifikation (Evidence)

### verify_guardrails
- PASS (`OK: All guardrail checks passed.`)

### healthcheck
- PASS (`[healthcheck] All checks passed`)

### pytest
- `pytest -q` **FAIL in dieser Umgebung** wegen fehlendem `playwright` bei E2E-Collection.
- `pytest -q --ignore=tests/e2e` PASS (619 passed, 7 skipped).

### relevante MIA-Zusatztests
- PASS (38 selected tests):
  - `tests/test_mia_flows_contract.py`
  - `tests/automation/test_mia_audit_events.py`
  - `tests/integration/test_intake_confirm_flow.py`
  - `tests/agents/test_cross_tool_flows.py`
  - `tests/agents/test_action_registry.py`
  - `tests/agents/test_action_registry_architecture.py`
  - `tests/integration/test_flow_ab_2000x.py`
  - `tests/integration/test_flow_ab_confirm_paths.py`

## 5) PR-Body-Entwurf (evidence-only)

### Was wurde geändert?
- Test-Fix in `tests/test_release_conductor_preflight.py`: Returncode-Erwartung für Warning-only-Preflight auf `0` gesetzt.
- Integrations-Readout mit Kompatibilitäts- und Risikobewertung erstellt.

### Warum?
- `healthcheck` brach wegen Testdrift: Script-Semantik (Warning-only => Exit 0) und Testerwartung (Exit 1) waren inkonsistent.
- Ziel war, nur kanonisch bereits konsistente Regeln zu stabilisieren, nicht neue Policy-Interpretationen einzuführen.

### Welche Gates wurden verbessert?
- Indirekt: `healthcheck` ist wieder grün, da die Preflight-Regression im Test entfernt wurde.
- Bestehende Gate-Härtungen (Guardrails, Gate-7, MIA-Confirm-Pfade) wurden durch Re-Tests verifiziert.

### Welche Risiken bleiben?
- Kein `origin` Remote vorhanden -> Baseline-Validierung gegen `origin/main` in diesem Clone nicht möglich.
- Integrations-Hotspots bleiben `manager_agent.py` und `launch_evidence_gate.sh` (hohes Konfliktpotenzial bei Parallelarbeit).
- E2E bleibt umgebungsabhängig (Playwright fehlt lokal).

### Was folgt als Nächstes?
1. Remote-Basis herstellen (`origin/main`) und Delta gegen lokalen Integrationsstand maschinell auswerten.
2. Hotspot-Dateien in klar separierte Module aufteilen (Gate-Registry, Router-Intent-Mapping), um Rebase-Konflikte zu senken.
3. E2E-Toolchain in CI strikt versionieren, damit `pytest -q` ohne Sonderflags reproduzierbar läuft.
