# CODEX-PROMPT — Lead Conversion v0 (Lead -> Deal -> Quote, confirm-first)

Repo: <REPO_ROOT>  
Base branch: main (nach Merge von Paket 1+2 oder mindestens Guard)  
Branch: feat/leads-conversion-v0

## ZIEL
Aus Lead einen Deal + Quote-Entwurf erzeugen, aber:
- Keine stille PII-Übernahme
- Bestätigungs-UI: Nutzer wählt explizit Felder/Mapping
- `entity_links` setzen: `link_type='converted_from'`
- Claim-Guard muss greifen (Lead muss frei oder vom User geclaimt sein)

## HARTE REGELN
- Keine neuen Dependencies
- Tenant safe
- Eventlog: PII-frei (nur IDs + mapping flags)
- READ_ONLY blockiert alle Mutationen

## ARBEITSPAKETE
### A) UI Flow
- Button „In Deal umwandeln“
- Confirm page: zeigt lead_number + optionale safe fields (kein rohes email/phone ohne Opt-in)
- Nutzer bestätigt: erstellt Deal/Quote draft

### B) Core
- `lead_convert_to_deal_quote(tenant_id, lead_id, actor_user_id, mapping)`
- Mapping nutzt bestehende Redaction/Sanitization-Helper
- Set `entity_links`:
  - `(deal) converted_from (lead)`
  - `(quote) derived_from (lead)` optional
- Events: `lead_converted`, `deal_created_from_lead` (IDs only)

### C) Tests
- positive flow (claim ok) -> entities created, links created
- blocked flow (lead claimed by other) -> 403
- tenant isolation
- eventlog payload no pii

## QUALITY
```bash
python -m compileall -q .
ruff check . --fix
ruff format .
pytest -q
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```
