from __future__ import annotations

from app.contracts.tool_contracts import build_contract_response, build_health_response
from app.modules.mail.logic import sla_unanswered_alert


def build_summary(tenant: str, *, messages: list[dict] | None = None, sla_hours: int = 24) -> dict:
    rows = list(messages or [])
    sla_metric = sla_unanswered_alert(rows, threshold_hours=sla_hours)
    status = "degraded" if sla_metric["alerts"] else "ok"
    degraded_reason = "mail_sla_violation" if status == "degraded" else ""
    return build_contract_response(
        tool="mail",
        status=status,
        degraded_reason=degraded_reason,
        metrics={
            "inbox_messages": len(rows),
            "sla_unanswered_alerts": sla_metric["alerts"],
            "sla_threshold_hours": sla_metric["threshold_hours"],
        },
        details={
            "tenant": str(tenant or "default"),
            "triage_categories": ["request", "invoice", "spam", "follow_up"],
            "confirm_gate": True,
            "read_only_default": True,
            "contract": {"read_only": True},
            "sla_metric": sla_metric,
        },
        tenant=tenant,
        contract_kind="summary",
    )


def build_health(tenant: str, *, messages: list[dict] | None = None, sla_hours: int = 24) -> tuple[dict, int]:
    summary = build_summary(tenant, messages=messages, sla_hours=sla_hours)
    return build_health_response(
        tool="mail",
        status=summary["status"],
        metrics=summary["metrics"],
        details=summary["details"],
        tenant=tenant,
        degraded_reason=summary.get("degraded_reason", ""),
        checks={
            "summary_contract": True,
            "backend_ready": True,
            "offline_safe": True,
            "confirm_gate": True,
        },
    )
