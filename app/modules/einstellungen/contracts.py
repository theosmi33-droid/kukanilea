from __future__ import annotations

from app.contracts.tool_contracts import build_contract_response


def build_summary(tenant: str) -> dict:
    return build_contract_response(
        tool="einstellungen",
        status="ok",
        metrics={
            "security_headers": 1,
            "admin_tools": 1,
        },
        details={
            "source": "settings.runtime",
            "pages": ["/settings", "/admin/logs", "/admin/audit"],
        },
        tenant=tenant,
    )


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["details"] = {
        **(payload.get("details") or {}),
        "checks": {
            "summary_contract": True,
            "backend_ready": True,
            "offline_safe": True,
        },
    }
    return payload, 200
