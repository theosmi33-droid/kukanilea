from __future__ import annotations
from app.agents.orchestrator import Orchestrator
from app.contracts.tool_contracts import build_contract_response, build_health_response

def build_summary(tenant: str) -> dict:
    # Basic availability check for orchestrator
    try:
        Orchestrator()
        active = True
    except Exception:
        active = False
        
    return build_contract_response(
        tool="messenger",
        status="ok" if active else "error",
        metrics={
            "orchestrator_ready": int(active),
            "local_llm_ready": 1,
        },
        details={
            "source": "orchestrator.status",
        },
        tenant=tenant,
        contract_kind="summary"
    )

def build_health(tenant: str) -> tuple[dict, int]:
    summary = build_summary(tenant)
    return build_health_response(
        tool="messenger",
        status=summary["status"],
        metrics=summary["metrics"],
        details=summary["details"],
        tenant=tenant,
        degraded_reason=summary.get("degraded_reason", ""),
        checks={
            "summary_contract": True,
            "backend_ready": summary["metrics"]["orchestrator_ready"] == 1,
            "offline_safe": True,
        }
    )
