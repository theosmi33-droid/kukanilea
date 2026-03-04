# Sovereign-11 Contract Standard

Alle Tool-Status APIs liefern jetzt ein einheitliches Schema:

- `GET /api/<tool>/summary`
- `GET /api/<tool>/health`

Schema:

```json
{
  "tool": "dashboard",
  "status": "ok|degraded|error",
  "updated_at": "ISO-8601",
  "metrics": {},
  "details": {},
  "degraded_reason": "optional"
}
```

Für `health` wird zusätzlich in `details.checks` geliefert:

- `summary_contract`
- `backend_ready`
- `offline_safe`

Tool-Liste (11): dashboard, upload, projects, tasks, messenger, email, calendar, time, visualizer, settings, chatbot.
