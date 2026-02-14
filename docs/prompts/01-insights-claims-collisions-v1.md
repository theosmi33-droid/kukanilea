# CODEX-PROMPT — Daily Insights v1: Lead Claims + Collisions (read-mostly, low-risk)

Repo: <REPO_ROOT>  
Base branch: main (nach Merge von leads-shared-inbox-claims-v1)  
Branch: feat/insights-claims-collisions-v1

## ZIEL
Erweitere Daily Insights um team-inbox-relevante Kennzahlen:
- unclaimed_leads_count
- claims_expiring_soon_count (<= 30 min)
- overdue_leads_by_owner (top 5)
- claim_collisions_count (letzte 24h)

Alles tenant-safe, offline-first, ohne neue Dependencies.

## NICHT-ZIELE
- Kein neues UI-Framework, nur bestehendes Dashboard.
- Keine Background-Jobs; Insights bleiben lazy + gecached wie vorhanden.

## HARTE REGELN
- Keine PII in Eventlog / Insights payloads (nur IDs/Counts/Hashes).
- Keine neuen Dependencies.
- Tenant-Isolation in jeder Query.
- READ_ONLY: Insights dürfen lesen (ok), aber keine Mutationen.

## ARBEITSPAKETE
### A) Collisions als Event definieren
- Wenn der Lead-Guard eine Mutation wegen fremdem Claim blockiert, schreibe `event_type='lead_claim_collision'`.
- `payload` allowlist: `{lead_id, claimed_by_user_id, route_key, ua_hash}`.
- `ua_hash = sha256(truncated user-agent)` als hex, keine Rohstrings.
- `route_key =` allowlisted short token (z.B. `lead_assign`, `lead_priority`, `lead_note_add`), keine URL.

### B) Insights Queries
- Nutze bestehendes `daily_insights_cache`.
- Query `unclaimed`: Leads ohne aktiven Claim (`lead_claims` join; `claimed_until >= now`).
- `expiring soon`: `claimed_until` between `now` and `now+30min`.
- `overdue by owner`: `lead.assigned_to` + `response_due < now`.
- `collisions 24h`: events where `event_type='lead_claim_collision'` and `created_at >= now-24h`.

### C) UI
- Ergänze Kacheln/Abschnitte im Daily-Insights-Template.
- Jede Kachel linkt auf passende Inbox-Filter (z.B. `/leads?filter=unclaimed`).

### D) Tests
- `test_insights_claims_counts.py` (tenant isolation, correct counts)
- `test_collision_event_emitted.py` (block -> collision event)
- `test_no_pii_in_insights.py` (payload allowlist)

## QUALITY
```bash
python -m compileall -q .
ruff check . --fix
ruff format .
pytest -q
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```
