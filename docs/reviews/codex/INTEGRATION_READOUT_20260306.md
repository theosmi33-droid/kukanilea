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
- Grund: `scripts/ops/launch_evidence_gate.sh` wurde in mehreren Integrationspaketen erweitert (u.a. MIA-Audit und Gate-7). Sequenzielle Erweiterungen sind kompatibel, aber bei parallelem Rebase konfliktanfällig.

### router/registry
- **Risiko: mittel bis hoch**.
- Grund: `manager_agent.py` wurde zuerst für sicheren Router angepasst und später erneut auf deklarative Registry umgebaut. Diese Datei ist Integrations-Hotspot.

### audit schema
- **Risiko: niedrig bis mittel**.
- Grund: stabiler Eventkatalog ist eingeführt; Konflikte entstehen primär, wenn neue Eventnamen ohne Aufnahme in `MIA_EVENTS_STABLE` kommen.

### approval engine
- **Risiko: mittel**.
- Grund: Approval-Logik ist an mehreren Ebenen vorhanden (Flow-Step-Confirm, Router-Confirm-Mode, Intake-Confirm-Pfade).

### flow framework
- **Risiko: mittel**.
- Grund: Framework ist deterministisch, aber gekoppelt an Action-Namen + Kontextfelder. Neue Flows ohne Registry-/Schema-Abgleich erzeugen Integrationsbrüche.

## 3) Verifikation (Evidence)

### verify_guardrails
- PASS (`OK: All guardrail checks passed.`)

### healthcheck
- PASS (`[healthcheck] All checks passed`)

### pytest
- `pytest -q` kann lokal wegen fehlendem Playwright bei E2E-Collection fehlschlagen.
- `pytest -q --ignore=tests/e2e` PASS.

## 4) Nächste Schritte
1. Remote-Basis stabilisieren (`origin/main`) und Delta gegen lokalen Integrationsstand maschinell auswerten.
2. Hotspot-Dateien in klar separierte Module aufteilen (Gate-Registry, Router-Intent-Mapping), um Rebase-Konflikte zu senken.
3. E2E-Toolchain in CI strikt versionieren, damit `pytest -q` ohne Sonderflags reproduzierbar läuft.
