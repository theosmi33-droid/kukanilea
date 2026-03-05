# Messenger/Chatbot Rückwärtskompatibilität

Stand: 2026-03-05

## Garantien

Die Contract-Härtung für Summary/Health ändert **nicht** die etablierten Messenger/Chatbot-Aliase:

- Eingabe-Aliase: `message`, `msg`, `q`
- Antwort-Aliase: `response` und `text` werden konsistent gespiegelt
- Bool-Feld `ok` bleibt erhalten

## Warum wichtig

Bestehende Messenger-Widgets und Bot-Clients senden teilweise unterschiedliche Request-Felder. Ohne Alias-Unterstützung würde es zu Breaking Changes kommen.

## Test-Abdeckung

- `tests/contracts/test_dashboard_chatbot_contract_payloads.py`
- `tests/contracts/test_required_schema_fields.py`
- `tests/contracts/test_summary_contracts.py`
