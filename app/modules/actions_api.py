from __future__ import annotations

from typing import Mapping

from flask import jsonify, request

from app.auth import login_required
from app.services.tool_action_service import (
    ActionDefinition,
    ToolActionTemplate,
)


ActionApiTemplate = ToolActionTemplate


def register_actions_endpoints(bp, templates: Mapping[str, ActionApiTemplate]) -> None:
    @bp.get("/api/<tool>/actions")
    @login_required
    def api_tool_actions(tool: str):
        template = templates.get(tool)
        if template is None:
            return jsonify(error="unknown_tool", tool=tool), 404
        return jsonify(template.list_actions_payload())

    @bp.post("/api/<tool>/actions/<name>")
    @login_required
    def api_tool_action_execute(tool: str, name: str):
        template = templates.get(tool)
        if template is None:
            return jsonify(error="unknown_tool", tool=tool), 404
        payload, status = template.execute(action_name=name, req=request)
        return jsonify(payload), status
