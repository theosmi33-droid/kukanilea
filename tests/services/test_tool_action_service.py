from __future__ import annotations

from flask import Flask

from app.services.tool_action_service import ActionDefinition, ToolActionTemplate


def _build_request(payload: dict[str, object]):
    app = Flask(__name__)
    ctx = app.test_request_context(json=payload)
    ctx.push()
    from flask import request

    return request, ctx


def test_execute_rejects_missing_required_field() -> None:
    template = ToolActionTemplate(
        tool="demo",
        actions=[
            ActionDefinition(
                name="create",
                title="Create",
                permission="read",
                risk="low",
                input_schema={"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}}},
                output_schema={"type": "object", "properties": {}},
                handler=lambda payload: {"ok": True, "payload": payload},
            )
        ],
    )

    request, ctx = _build_request({})
    try:
        payload, status = template.execute(action_name="create", req=request)
    finally:
        ctx.pop()

    assert status == 400
    assert payload["error"] == "title_missing"


def test_execute_rejects_guardrail_violation() -> None:
    template = ToolActionTemplate(
        tool="demo",
        actions=[
            ActionDefinition(
                name="query",
                title="Query",
                permission="read",
                risk="low",
                input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}},
                output_schema={"type": "object", "properties": {}},
                handler=lambda payload: {"ok": True, "payload": payload},
            )
        ],
    )

    request, ctx = _build_request({"prompt": "DROP TABLE users"})
    try:
        payload, status = template.execute(action_name="query", req=request)
    finally:
        ctx.pop()

    assert status == 400
    assert payload["error"] == "guardrails_blocked"


def test_list_actions_uses_registry_fallback_when_template_empty() -> None:
    from app.tools.action_registry import action_registry
    from app.tools.base_tool import BaseTool

    previous = dict(action_registry._actions_by_name)
    action_registry._actions_by_name.clear()

    class DemoTool(BaseTool):
        name = "demo"

    try:
        action_registry.register_tool(DemoTool())
        template = ToolActionTemplate(tool="demo", actions=[])

        payload = template.list_actions_payload()

        assert payload["ok"] is True
        assert payload["tool"] == "demo"
        assert any(item["name"] == "demo.execute" for item in payload["actions"])
    finally:
        action_registry._actions_by_name.clear()
        action_registry._actions_by_name.update(previous)
