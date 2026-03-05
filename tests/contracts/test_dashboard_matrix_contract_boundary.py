from __future__ import annotations

import inspect

import app.web as web


def test_dashboard_tool_matrix_endpoint_uses_contract_builder_boundary():
    source = inspect.getsource(web.api_dashboard_tool_matrix)

    assert "build_tool_matrix" in source
    assert "core." not in source
    assert "from app import core" not in source
