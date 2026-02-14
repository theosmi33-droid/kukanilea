# Automation + Daily Insights v1

## Sicherheitsmodell
- Offline-only: keine Netzwerk-Integrationen.
- Kein eval/exec, kein Shell-Exec.
- DSL mit Allowlist für Conditions und Actions.
- Harte Bounds:
  - `max_actions_per_run` (default 50)
  - `max_targets_per_rule` (default 25)
- READ_ONLY blockiert alle mutierenden Automation-Aktionen.

## Conditions (v1)
- `lead_overdue`
- `lead_screening_stale`
- `lead_priority_high_unassigned`
- `task_overdue`

## Actions (v1)
- `create_task`
- `lead_pin`
- `lead_set_priority`
- `lead_assign`
- `lead_set_response_due`
- `lead_add_event`

## Beispielregel 1
Condition:
```json
{"days_overdue":1,"status_in":["new","contacted","qualified"],"priority_in":["normal","high"]}
```
Actions:
```json
[{"kind":"create_task","title_template":"LEAD #{lead_id_short} follow-up","priority":"HIGH","assign_to":"actor","link_lead_id":true},{"kind":"lead_pin","value":true}]
```

## Beispielregel 2
Condition:
```json
{"hours_in_screening":24}
```
Actions:
```json
[{"kind":"lead_add_event","event_type":"automation_screening"},{"kind":"lead_set_response_due","hours_from_now":24}]
```

## Insights
`/insights/daily` erzeugt beim ersten Aufruf die Tagesmetriken und cached sie in `daily_insights_cache`.
Es gibt keinen Background-Job in v1.
