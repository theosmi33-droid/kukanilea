# Manager Agent Router – How to run

## Tests ausführen
```bash
pytest -q tests/core/test_agent_router.py tests/core/test_confirm_gate.py tests/integration/test_chat_to_action_flow.py
```

## Quick smoke in Python
```bash
python - <<'PY'
from app.core.agent_router import plan_actions
from app.core.action_executor import ActionExecutor

plan = plan_actions("erstelle task für tenant alpha", {"tenant": "alpha", "user_id": "u1"})
executor = ActionExecutor({"core.write_action": lambda p: {"ok": True, "payload": p}})
proposal = executor.execute_plan(plan, dry_run=False)
print(proposal)
executor.confirm(proposal["proposal_id"], approved=True)
print(executor.execute_plan(plan, dry_run=False, proposal_id=proposal["proposal_id"]))
PY
```
