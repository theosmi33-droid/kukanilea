# CONTRACTS HARDENING REPORT — 2026-03-05

## Scope

PR #314 wurde auf "hart standardisiert" gehärtet für `contracts-core`.

### Ziele
1. Einheitliches `summary/health` Schema für alle 11 Tools.
2. Pflichtfelder strikt durchgesetzt: `tool,status,updated_at,metrics,details,details.contract.version,details.contract.read_only`.
3. Negative Tests ergänzt (fehlende Felder, falsche Datentypen, degraded/error statt 500).
4. Dashboard-Tool-Matrix auf Contract-Boundary abgesichert.
5. Rückwärtskompatibilität für Messenger/Chatbot dokumentiert.

## Implementierung

- Zentrale Contract-Normalisierung + Validation in `app/contracts/tool_contracts.py`.
- Collector-Vertragsverletzungen werden als `degraded` abgefangen (`collector_contract_invalid`) statt Absturz.
- Collector-Exceptions werden in standardisierte `error`-Payloads überführt.
- Matrix-Endpunkt bleibt read-only contract consumer via `build_tool_matrix`.

## Test-Gates

### CI_GATE (Pflicht)

```bash
pytest -q tests/contracts tests/integration/test_dashboard_tool_matrix.py
```

Ergebnis: **61 passed**.

### Negative Test-Abdeckung (mind. 4)

Enthaltene Negativfälle:
- fehlende Felder (`_normalize_contract_payload({})`)
- falsche Datentypen (`tool`, `updated_at`, `metrics`, `details`)
- Collector-Vertragsverletzung (`metrics/details/degraded_reason` falscher Typ)
- Collector-Exception → `error` Payload statt 500

## Hard-Gates Check

- **MIN_SCOPE**: erfüllt (10 Dateien geändert).
- **MIN_TESTS**: erfüllt (>=10; aktuell 61 Tests im Gate-Lauf, mehrere negative Tests).
- **CI_GATE**: erfüllt.
- **Evidence-Datei**: vorhanden (`CONTRACTS_HARDENING_REPORT_20260305.md`).
