from __future__ import annotations

from datetime import UTC, datetime

from app.modules.mail.logic import sla_unanswered_alert


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(tenant: str, *, messages: list[dict] | None = None, sla_hours: int = 24) -> dict:
    rows = list(messages or [])
    sla_metric = sla_unanswered_alert(rows, threshold_hours=sla_hours)
    return {
        "tool": "email",
        "status": "degraded" if sla_metric["alerts"] else "ok",
        "updated_at": _now_iso(),
        "metrics": {
            "inbox_messages": len(rows),
            "sla_unanswered_alerts": sla_metric["alerts"],
            "sla_threshold_hours": sla_metric["threshold_hours"],
        },
        "details": {
            "tenant": str(tenant or "default"),
            "triage_categories": ["request", "invoice", "spam", "follow_up"],
            "confirm_gate": True,
            "read_only_default": True,
            "contract": {"version": "2026-03-05", "read_only": True},
            "sla_metric": sla_metric,
        },
    }


def build_health(tenant: str, *, messages: list[dict] | None = None, sla_hours: int = 24) -> tuple[dict, int]:
    payload = build_summary(tenant, messages=messages, sla_hours=sla_hours)
    payload["details"] = {
        **(payload.get("details") or {}),
        "checks": {
            "summary_contract": True,
            "backend_ready": True,
            "offline_safe": True,
            "confirm_gate": True,
        },
    }
    return payload, 200 if payload.get("status") in {"ok", "degraded"} else 503
