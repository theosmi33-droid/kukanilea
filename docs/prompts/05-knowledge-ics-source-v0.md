# CODEX-PROMPT — Knowledge: ICS Calendar Source v0 (minimal parser, RFC unfolding, hard limits)

Repo: <REPO_ROOT>  
Base branch: main (nach Merge von Guard/CI empfohlen)  
Branch: feat/knowledge-ics-source-v0

## ZIEL
Upload `.ics`, policy-gated, extrahiere nur:
- DTSTART
- DTEND
- SUMMARY (sanitized + truncated)
- LOCATION (sanitized + truncated)

Speichere daraus `knowledge_chunks` (`source_type='calendar'`). Keine Roh-ICS Speicherung.

## SICHERHEIT
- Keine neuen Dependencies.
- Policy default deny: `allow_calendar=0`.
- RFC Unfolding MUSS vor Parsing passieren:
  - Entferne jedes `CRLF` gefolgt von `SPACE` oder `HTAB` (unfold).
- Ignoriere/Droppe: `ATTENDEE`, `ORGANIZER`, `DESCRIPTION`, `COMMENT`, `CONTACT`, `ATTACH`, `URL`, `RRULE` (v0)
- Limits:
  - `max_upload_bytes` (z.B. 256KB)
  - `max_events_parsed` (z.B. 10)
  - `max_chunks_written` (z.B. 50)
  - `max_line_len` after unfolding (z.B. 2k)
- Eventlog payload: ids + sha256 + counts only (no content)

## IMPLEMENTATION HINWEIS
- Parser line-based:
  - Unfold bytes -> text (`utf-8`, `errors='replace'`), strip NUL
  - Scan `BEGIN:VEVENT..END:VEVENT` blocks, stop after `max_events_parsed`
  - Within block accept properties with optional params:
    - `DTSTART` or `DTSTART;...:`
    - `DTEND` or `DTEND;...:`
    - `SUMMARY` or `SUMMARY;...:`
    - `LOCATION` or `LOCATION;...:`
  - Parse as: key up to `:` then value after `:`
  - Date parsing support:
    - `YYYYMMDD`
    - `YYYYMMDDTHHMMSSZ`
    - `YYYYMMDDTHHMMSS`
    - If unknown -> drop field

## SCHEMA
- `knowledge_ics_sources`: filename, sha, event_count, created_at, tenant_id
- `knowledge_ics_ingest_log` (optional): status, counts, policy_violation

## TESTS (mit fixtures)
- `google_calendar_min.ics` (folded lines)
- `apple_ical_min.ics`
- `outlook_min.ics`
- `malicious_attach.ics` (ATTACH large) -> ignored + limits hold
- `rrule.ics` -> ignored (no expansion)

## QUALITY
```bash
python -m compileall -q .
ruff check . --fix
ruff format .
pytest -q
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```
