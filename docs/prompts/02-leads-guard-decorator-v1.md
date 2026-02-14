# CODEX-PROMPT — Lead Guard Decorator v1 (single choke-point)

Repo: <REPO_ROOT>  
Base branch: main (nach Merge von leads-shared-inbox-claims-v1)  
Branch: feat/leads-guard-decorator-v1

## ZIEL
Erzeuge einen zentralen Decorator `@require_lead_access(...)` für `app/web.py`, der:
1) login/tenant resolved
2) READ_ONLY -> 403 (json/html consistent)
3) claim-guard -> `lead_require_claim_or_free(...)` (oder `require_claim=True`)
4) bei collision: 403 + structured error
5) (optional) collision event emitted (wenn nicht in Paket 1 schon erledigt)

## WICHTIG
- Muss für HTML + JSON identisch funktionieren:
  - HTML: flash/banner + 403 view
  - JSON: `{"error":"lead_claimed","claimed_by":"<id>","lead_id":"<id>","route":"<route_key>"}` + 403
- `route_key` allowlist, keine URL strings.

## ARBEITSPAKETE
### A) Decorator implementieren (`web.py`)
- `@require_lead_access(route_key: str, require_claim: bool = False)`
- Nutzt `current_user/current_tenant` wie üblich.
- Ruft `lead_require_claim_or_free(tenant_id, lead_id, user_id, ...)` auf.
- On block: optional event `lead_claim_collision` (wenn Paket 1 nicht merged).

### B) Apply Coverage
- Ersetze alle mutierenden Lead-Routen durch Decorator:
  - `screen/accept`, `screen/ignore`
  - `priority toggle`, `pin toggle`
  - `assign`, `response_due` changes
  - `blocklist add`
  - `lead note/comment` additions (falls existieren)
- Keine stillen Ausnahmen.

### C) Coverage-Test (verhindert „vergessene Route“)
- `test_lead_guard_decorator_coverage.py`:
  - Parse `app.web` routes.
  - Für alle `/leads/<id>/...` POST/DELETE endpoints: assert decorator present ODER explicit allowlist mit Begründung.
  - Fail-closed: Neue Route bricht Test bis sie abgesichert ist.

### D) Tests für JSON/HTML parity
- 403 status, stable error schema, no PII.

## QUALITY
```bash
python -m compileall -q .
ruff check . --fix
ruff format .
pytest -q
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```
