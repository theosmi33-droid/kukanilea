# DOMAIN_OWNERSHIP_REPORT_20260304_201026

## Ziel
Abgleich der Overlap-Regeln mit den tatsächlichen Dateiänderungen dieser Mission.

## Geänderte fachliche Dateien
- `app/contracts/tool_contracts.py`
- `tests/contracts/test_dashboard_chatbot_contract_payloads.py`

## Overlap-Check Ergebnisse
### Dashboard-Reiter
- Command: `python3 scripts/dev/check_domain_overlap.py --reiter dashboard --files app/contracts/tool_contracts.py tests/contracts/test_dashboard_chatbot_contract_payloads.py --json`
- Ergebnis: `DOMAIN_OVERLAP_DETECTED`
- Grund: `app/contracts/tool_contracts.py` liegt außerhalb Dashboard-Allowlist.

### Floating-Widget-Chatbot-Reiter
- Command: `python3 scripts/dev/check_domain_overlap.py --reiter floating-widget-chatbot --files app/contracts/tool_contracts.py tests/contracts/test_dashboard_chatbot_contract_payloads.py --json`
- Ergebnis: `DOMAIN_OVERLAP_DETECTED`
- Grund: Beide Dateien außerhalb der Reiter-Allowlist.

## Ownership-Entscheidung
- Änderung ist absichtlich im Shared Contract Layer, um Domain-Drift zu reduzieren und für alle 11 Tools denselben Contract zu erzwingen.
- Kein Domain-Codepfad für schreibende Business-Aktionen wurde ergänzt.
- Scope-Request dokumentiert die zentrale Contract-Layer-Ausnahme: `docs/scope_requests/core_contract_layer_20260304_201026.md`.
