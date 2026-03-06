from __future__ import annotations

import subprocess
import sys

from flask import Flask

from app.core.tool_loader import load_all_tools, verify_tool_interface
from app.tools.base_tool import BaseTool


class _ValidTool(BaseTool):
    name = "valid_tool"
    description = "A valid tool for contract testing"
    input_schema = {"type": "object"}

    def run(self, **kwargs):
        return kwargs


class _BrokenTool(BaseTool):
    name = ""
    description = ""
    input_schema = "not-a-dict"
    endpoint = "relative-path"

    run = None


def test_verify_tool_interface_accepts_valid_tool():
    result = verify_tool_interface(_ValidTool())
    assert result.valid is True
    assert result.errors == []


def test_verify_tool_interface_rejects_invalid_tool():
    result = verify_tool_interface(_BrokenTool())
    assert result.valid is False
    assert any("name must be a non-empty string" in err for err in result.errors)
    assert any("description must be a non-empty string" in err for err in result.errors)
    assert any("input_schema must be a dict" in err for err in result.errors)
    assert any("run must be callable" in err for err in result.errors)
    assert any("all endpoints must be absolute paths" in err for err in result.errors)


def test_load_all_tools_records_report_in_app_config():
    app = Flask(__name__)
    report = load_all_tools(app)

    assert report == app.config["TOOL_LOADER_REPORT"]
    assert isinstance(app.config["TOOL_LOADER_LOADED_TOOLS"], list)
    assert isinstance(app.config["TOOL_LOADER_FAILED_TOOLS"], list)
    assert len(report["loaded_tools"]) >= 1


def test_verify_tools_cli_exits_zero_when_all_tools_pass():
    proc = subprocess.run(
        [sys.executable, "scripts/dev/verify_tools.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Core Tool Interface Verification" in proc.stdout
