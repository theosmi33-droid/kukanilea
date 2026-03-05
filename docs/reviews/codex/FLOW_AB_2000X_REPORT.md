# FLOW A/B 2000X REPORT

## Scope
End-to-End Härtung für:
- **Flow A (Inbox/Intake):** Mail/Messenger → Intake-Envelope → Task/Projekt/Termin
- **Flow B (Upload Pipeline):** Upload → OCR/Extraktion-Readiness → Frist/Zuordnung → Task/Kalender
- **Cross-Flow:** Intake + Upload + Summary/Health Contracts in einer Kette

## Implementierte Fixes
1. **Einheitliches Contract-Surface für Intake eingeführt**
   - `CONTRACT_TOOLS` um `intake` ergänzt.
   - `SUMMARY_COLLECTORS` um `_collect_intake_summary` erweitert.
   - Damit sind `/api/intake/summary` und `/api/intake/health` über den generischen Tool-Contract Endpoint verfügbar.

2. **Flow A/B 2000X Integrationsabsicherung hinzugefügt**
   - Neuer Integrationstest `tests/integration/test_flow_ab_2000x.py`.
   - Simuliert und verifiziert:
     - 100 Intake-Fälle (mail/messenger/mixed) à 8 Schritte.
     - 80 Dokumentfälle (pdf/image/malformed) à 8 Schritte.
     - 20 Cross-Flow-Fälle à 20 Schritte.
   - Gesamtledger wird testseitig als `total_steps >= 2000` erzwungen (aktuell 2040 Schritte inkl. Stabilization-Lane).

## Fehlerklassen-Matrix + Fixnachweise

| Fehlerklasse | Ursache | Fix | Nachweis |
|---|---|---|---|
| Missing tool contract for intake | Intake nicht in `CONTRACT_TOOLS`/Collector-Matrix | `intake` Collector + Tool-Liste ergänzt | `pytest -q tests/contracts` grün |
| Confirm-gate bypass risk | Intake Execute ohne explizite Bestätigung | Confirm-Pfad in Stresslauf stets geprüft (blocked + confirmed) | `test_flow_ab_action_ledger_reaches_2000` |
| Upload malformed docs handling | Unsupported extensions müssen sicher rejecten | `.exe` Fälle erzeugen deterministischen `UNSUPPORTED_EXTENSION` Pfad | `test_flow_ab_action_ledger_reaches_2000` |
| Cross-flow contract drift | Task/Calendar/Upload Health Konsistenz fehlt unter Last | Pro Cross-Flow Fall Summary/Health Endpoints validiert | `test_flow_ab_action_ledger_reaches_2000` |

## KPI Delta

| KPI | Vorher | Nachher | Delta |
|---|---:|---:|---:|
| Flow-A/B Ledger Coverage | n/a | **2040 Schritte** | +2040 |
| Contracted tools mit Summary/Health | 11 | **12** (inkl. intake) | +1 |
| Contracts Testpassrate | 57/57 | **61/61** | +4 |

## Ausführung / Validation
- `pytest -q tests/integration/test_flow_ab_2000x.py`
- `pytest -q tests/contracts`
- `pytest -q tests -k "intake or upload or calendar or task"` *(blockiert bei Collection, fehlendes `playwright` Modul)*
- `./scripts/ops/healthcheck.sh` *(blockiert beim selben fehlenden `playwright` Modul in E2E Collection)*

## Risiko / offene Punkte
- Umgebung benötigt `playwright` Python Paket für vollständigen E2E-Teil der Mandatory-Testkommandos.
- Kernfunktionale Integrations- und Contract-Pfade sind lokal grün.
