# Tool Read-Contracts (`summary` / `health`)

Alle Tools liefern stabilisierte Read-Contracts über:

- `GET /api/<tool>/summary`
- `GET /api/<tool>/health`

## Standard Payload (v2026-03-05)

```json
{
  "tool": "X",
  "status": "ok|degraded|down",
  "ts": "ISO-8601",
  "summary": {},
  "warnings": [],
  "links": []
}
```

## Status-Code Policy

- `ok` => HTTP `200`
- `degraded` => HTTP `503` (mit gültigem JSON-Contract)
- `down` => HTTP `503` für health, sonst konsistent `500/503` je Endpoint-Policy

## Tool Matrix

| Tool | Summary Endpoint | Health Endpoint | Contract Status |
|---|---|---|---|
| dashboard | `/api/dashboard/summary` | `/api/dashboard/health` | PASS |
| upload | `/api/upload/summary` | `/api/upload/health` | PASS |
| projects | `/api/projects/summary` | `/api/projects/health` | PASS |
| tasks | `/api/tasks/summary` | `/api/tasks/health` | PASS |
| messenger | `/api/messenger/summary` | `/api/messenger/health` | PASS |
| email | `/api/email/summary` | `/api/email/health` | PASS |
| calendar | `/api/calendar/summary` | `/api/calendar/health` | PASS |
| time | `/api/time/summary` | `/api/time/health` | PASS |
| visualizer | `/api/visualizer/summary` | `/api/visualizer/health` | PASS |
| settings | `/api/settings/summary` | `/api/settings/health` | PASS |
| chatbot | `/api/chatbot/summary` | `/api/chatbot/health` | PASS |
| kalender | `/api/kalender/summary` | `/api/kalender/health` | PASS |
| aufgaben | `/api/aufgaben/summary` | `/api/aufgaben/health` | PASS |
| zeiterfassung | `/api/zeiterfassung/summary` | `/api/zeiterfassung/health` | PASS |
| projekte | `/api/projekte/summary` | `/api/projekte/health` | PASS |
| einstellungen | `/api/einstellungen/summary` | `/api/einstellungen/health` | PASS |

## JSON Beispiele

### `GET /api/tasks/summary`

```json
{
  "tool": "tasks",
  "status": "ok",
  "ts": "2026-03-05T10:00:00+00:00",
  "summary": {
    "tasks_total": 3,
    "tasks_open": 1,
    "tenant": "KUKANILEA"
  },
  "warnings": [],
  "links": []
}
```

### `GET /api/upload/health` (degraded)

```json
{
  "tool": "upload",
  "status": "degraded",
  "ts": "2026-03-05T10:00:00+00:00",
  "summary": {
    "pending_items": 0,
    "accepts_batch": 1,
    "tenant": "KUKANILEA",
    "checks": {
      "summary_contract": true,
      "backend_ready": false,
      "offline_safe": true
    }
  },
  "warnings": ["pending_pipeline_unavailable"],
  "links": []
}
```
