# Gate 7 Smoke Evidence

- Timestamp: 2026-03-07T03:11:30+00:00
- Overall: **PASS**
- Audit events: 14

| Check | Result | Detail |
|---|---|---|
| lokales_modell_aktiv | PASS | provider=mock; fallback=mock |
| summary_read_api_ok | PASS | status=routed; reason=; action=dashboard.summary.read; mode=read |
| write_confirm_gate_erzwungen | PASS | status=confirm_required; reason=approval_required; action=tasks.task.create; mode=confirm |
| write_mit_confirm_moeglich | PASS | status=routed; reason=; action=tasks.task.create; mode=confirm |
| injection_blockiert | PASS | status=blocked; reason=prompt_injection; action=safe_fallback; mode=propose |
| unknown_intent_fallback | PASS | status=needs_clarification; reason=unknown_intent; action=safe_follow_up; mode=propose |
| schema_validation_blockiert | PASS | status=blocked; reason=schema_validation_failed; action=dashboard.summary.read; mode=read |
| external_call_offline_blockiert | PASS | status=offline_blocked; reason=external_calls_disabled; action=messenger.message.reply; mode=confirm |
| audit_logs_vorhanden | PASS | events=14; types=['approval.approve', 'approval.create', 'manager_agent.blocked', 'manager_agent.confirm_blocked', 'manager_agent.needs_clarification', 'manager_agent.offline_blocked', 'manager_agent.routed'] |

## Audit Event Types

- `manager_agent.routed`
- `approval.create`
- `manager_agent.confirm_blocked`
- `approval.create`
- `manager_agent.confirm_blocked`
- `approval.approve`
- `manager_agent.routed`
- `manager_agent.blocked`
- `manager_agent.needs_clarification`
- `manager_agent.blocked`
- `approval.create`
- `manager_agent.confirm_blocked`
- `approval.approve`
- `manager_agent.offline_blocked`
