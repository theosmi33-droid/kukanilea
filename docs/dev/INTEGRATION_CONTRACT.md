# Integration Contract (Sovereign 11)

Alle Tool-Domains liefern standardisierte Contract-Endpunkte:

- `GET /api/<tool>/summary`
- `GET /api/<tool>/health`

## JSON-Schema

```json
{
  "tool": "<tool>",
  "status": "ok|healthy|degraded|down",
  "updated_at": "ISO-8601",
  "metrics": {},
  "details": {}
}
```

## Governance-Matrix (11 Tools)

| Tool | Summary | Health | Status |
|---|---|---|---|
| dashboard | `/api/dashboard/summary` | `/api/dashboard/health` | active |
| upload | `/api/upload/summary` | `/api/upload/health` | active |
| projects | `/api/projects/summary` | `/api/projects/health` | active |
| tasks | `/api/tasks/summary` | `/api/tasks/health` | active |
| messenger | `/api/messenger/summary` | `/api/messenger/health` | active |
| email | `/api/email/summary` | `/api/email/health` | active |
| calendar | `/api/calendar/summary` | `/api/calendar/health` | active |
| time | `/api/time/summary` | `/api/time/health` | active |
| visualizer | `/api/visualizer/summary` | `/api/visualizer/health` | active |
| settings | `/api/settings/summary` | `/api/settings/health` | active |
| chatbot | `/api/chatbot/summary` | `/api/chatbot/health` | active |

## Dashboard Aggregation

Das Dashboard konsumiert ausschließlich Contract-Daten über:

- `GET /api/dashboard/contracts`

Keine Cross-Domain-DB-Zugriffe im Dashboard-Aggregator.
