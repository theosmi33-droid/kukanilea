from __future__ import annotations

import pytest

from app.tools.time_tool import TimeTool


def test_time_tool_rejects_mismatched_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.time_tool.get_tenant_id", lambda: "TENANT_A")
    tool = TimeTool()

    with pytest.raises(PermissionError, match="tenant_mismatch"):
        tool.run(tenant_id="TENANT_B", action="start")


def test_time_tool_requires_tenant_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.time_tool.get_tenant_id", lambda: None)
    tool = TimeTool()

    result = tool.run(tenant_id="TENANT_A", action="start")

    assert result["status"] == "error"
    assert result["error"] == "tenant_context_missing"


def test_time_tool_binds_to_active_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.time_tool.get_tenant_id", lambda: "TENANT_A")
    tool = TimeTool()

    result = tool.run(tenant_id="TENANT_A", action="start", project_id="proj-1")

    assert result["status"] == "started"
    assert result["tenant_id"] == "TENANT_A"
    assert result["project_id"] == "proj-1"
