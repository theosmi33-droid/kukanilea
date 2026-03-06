# Sovereign-11 Contract Standard

Alle Tool-Status APIs liefern ein einheitliches, strikt validiertes Schema:

- `GET /api/<tool>/summary`
- `GET /api/<tool>/health`

## Pflichtfelder (11/11 Tools)

```json
{
  "tool": "dashboard",
  "status": "ok|degraded|error",
  "updated_at": "ISO-8601",
  "metrics": {},
  "details": {
    "contract": {
      "version": "2026-03-05",
      "read_only": true
    }
  },
  "degraded_reason": "optional"
}
```

Wenn ein Collector ein fehlerhaftes Shape liefert (fehlende Felder/falsche Typen), wird der Payload normalisiert und als `degraded` mit `degraded_reason=contract_normalized` zurückgegeben. Bei Runtime-Fehlern kommt `error` statt HTTP-500.

## Health Zusatzfelder

Für `health` wird zusätzlich in `details.checks` geliefert:

- `summary_contract`
- `backend_ready`
- `offline_safe`

## Dashboard-Tool-Matrix Boundary

`GET /api/dashboard/tool-matrix` konsumiert ausschließlich Contract-Payloads aus `app.contracts.tool_contracts.build_tool_matrix`.
Es gibt keine versteckten Core-Imports im Matrix-Endpoint.

## Rückwärtskompatibilität (Messenger/Chatbot)

Bestehende Messenger/Chatbot Payload-Aliase bleiben erhalten:

- Request: `message`, `msg`, `q`
- Response: `ok`, `response` (inklusive Spiegelung auf `text`)

Damit bleiben bestehende Frontends/Bots kompatibel, während die Summary/Health-Contracts auf den harten Pflichtschema-Standard gebracht werden.

Tool-Liste (11): dashboard, upload, projects, tasks, messenger, email, calendar, time, visualizer, settings, chatbot.


## Actions API Erweiterung

Für write-fähige Tool-Contracts ist ein Draft für ein standardisiertes Actions-Interface dokumentiert:

- Spec: `docs/contracts/actions_api/TOOL_ACTIONS_API_SPEC.md`
- JSON-Schema-Drafts: `docs/contracts/actions_api/schemas/*.json`

## Tool Actions Interface (Legacy Draft)

Zusätzlich liegt ein älterer Interface-Entwurf für Teams vor, die mit der vorherigen Struktur arbeiten:

- Spec: `docs/contracts/TOOL_ACTIONS_INTERFACE.md`
- Schemas (Draft 2020-12):
  - `docs/contracts/schemas/tool_actions_list.schema.json`
  - `docs/contracts/schemas/tool_action_execute.request.schema.json`
  - `docs/contracts/schemas/tool_action_execute.response.schema.json`
  - `docs/contracts/schemas/tool_action_audit_event.schema.json`
  - `docs/contracts/schemas/tool_action_idempotency_record.schema.json`
