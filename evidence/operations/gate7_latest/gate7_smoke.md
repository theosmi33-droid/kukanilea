# Gate 7 Smoke Evidence

- Timestamp: 2026-03-06T22:00:20+00:00
- Overall: **PASS**
- Audit events: 4

| Check | Result | Detail |
|---|---|---|
| lokales_modell_aktiv | PASS | provider=mock |
| summary_read_api_ok | PASS | status=routed; action=dashboard_summary; mode=read |
| write_confirm_gate_erzwungen | PASS | status=confirm_required; reason=confirm_gate |
| write_mit_confirm_moeglich | PASS | status=routed; action=task_create |
| injection_blockiert | PASS | status=blocked; reason=prompt_injection |
| audit_logs_vorhanden | PASS | events=4; types=['manager_agent.blocked', 'manager_agent.confirm_blocked', 'manager_agent.routed'] |

## Audit Event Types

- `manager_agent.routed`
- `manager_agent.confirm_blocked`
- `manager_agent.routed`
- `manager_agent.blocked`
