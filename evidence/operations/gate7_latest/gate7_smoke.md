# Gate 7 Smoke Evidence

- Timestamp: 2026-03-06T22:34:15+00:00
- Overall: **PASS**
- Audit events: 4

| Check | Result | Detail |
|---|---|---|
| lokales_modell_aktiv | PASS | provider=mock; fallback=mock |
| summary_read_api_ok | PASS | status=routed; reason=; action=dashboard.summary.read; mode=read |
| write_confirm_gate_erzwungen | PASS | status=confirm_required; reason=confirm_gate; action=tasks.task.create; mode=confirm |
| write_mit_confirm_moeglich | PASS | status=routed; reason=; action=tasks.task.create; mode=confirm |
| injection_blockiert | PASS | status=blocked; reason=prompt_injection; action=safe_fallback; mode=propose |
| audit_logs_vorhanden | PASS | events=4; types=['manager_agent.blocked', 'manager_agent.confirm_blocked', 'manager_agent.routed'] |

## Audit Event Types

- `manager_agent.routed`
- `manager_agent.confirm_blocked`
- `manager_agent.routed`
- `manager_agent.blocked`
