from __future__ import annotations

import json
from pathlib import Path

README = Path("docs/contracts/README.md")
SPEC = Path("docs/contracts/TOOL_ACTIONS_INTERFACE.md")
SCHEMAS = Path("docs/contracts/schemas")

REQUIRED_SCHEMA_FILES = {
    "tool_actions_list.schema.json",
    "tool_action_execute.request.schema.json",
    "tool_action_execute.response.schema.json",
    "tool_action_audit_event.schema.json",
    "tool_action_idempotency_record.schema.json",
}


def _read(path: Path) -> str:
    assert path.exists(), f"missing: {path}"
    return path.read_text(encoding="utf-8")


def test_actions_interface_docs_exist() -> None:
    assert README.exists()
    assert SPEC.exists()
    assert SCHEMAS.exists()


def test_readme_mentions_actions_interface_section() -> None:
    text = _read(README)
    assert "Tool Actions Interface (Legacy Draft)" in text
    assert "docs/contracts/TOOL_ACTIONS_INTERFACE.md" in text


def test_spec_contains_expected_endpoints_and_contract_shapes() -> None:
    text = _read(SPEC)
    assert "GET /api/<tool>/actions" in text
    assert "POST /api/<tool>/actions/<name>" in text
    assert "Idempotency-Key" in text


def test_spec_contains_permissions_confirm_gate_and_audit_sections() -> None:
    text = _read(SPEC)
    assert "Permissions Model" in text
    assert "Confirm-Gate Protocol" in text
    assert "Audit Event Schema" in text


def test_schema_files_exist() -> None:
    actual = {p.name for p in SCHEMAS.glob("*.json")}
    assert REQUIRED_SCHEMA_FILES.issubset(actual)


def test_schema_files_are_valid_json_schemas() -> None:
    for name in REQUIRED_SCHEMA_FILES:
        data = json.loads(_read(SCHEMAS / name))
        assert isinstance(data, dict)
        assert "$schema" in data
        assert data.get("type") == "object"


def test_actions_list_schema_enforces_actions_array() -> None:
    data = json.loads(_read(SCHEMAS / "tool_actions_list.schema.json"))
    props = data.get("properties", {})
    assert "actions" in props
    assert props["actions"].get("type") == "array"
