from __future__ import annotations

from pathlib import Path

from app.contracts.tool_contracts import CONTRACT_TOOLS


def test_all_contract_tools_have_global_summary_and_health_route_contracts() -> None:
    source = Path("app/web.py").read_text(encoding="utf-8")

    assert '@bp.get("/api/<tool>/summary")' in source
    assert '@bp.get("/api/<tool>/health")' in source
    assert len(CONTRACT_TOOLS) == 11
