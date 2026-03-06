from __future__ import annotations

import json
from pathlib import Path

README = Path("docs/contracts/README.md")
SPEC = Path("docs/contracts/actions_api/TOOL_ACTIONS_API_SPEC.md")
SCHEMAS_DIR = Path("docs/contracts/actions_api/schemas")

EXPECTED_SCHEMAS = {
    "tool_action_audit_event.schema.json",
    "tool_action_confirm_token_claims.schema.json",
    "tool_action_execute.request.schema.json",
    "tool_action_execute.response.schema.json",
    "tool_actions_list.response.schema.json",
}


def _read(path: Path) -> str:
    assert path.exists(), f"missing: {path}"
    return path.read_text(encoding="utf-8")


def test_actions_api_docs_exist() -> None:
    assert README.exists()
    assert SPEC.exists()
    assert SCHEMAS_DIR.exists()


def test_readme_references_actions_api_extension() -> None:
    text = _read(README)
    assert "Actions API Erweiterung" in text
    assert "docs/contracts/actions_api/TOOL_ACTIONS_API_SPEC.md" in text


def test_spec_declares_actions_endpoints() -> None:
    text = _read(SPEC)
    assert "GET /api/<tool>/actions" in text
    assert "POST /api/<tool>/actions/<name>" in text


def test_spec_declares_confirm_gate_flow() -> None:
    text = _read(SPEC)
    assert "propose -> confirm -> execute" in text
    assert "confirm_token" in text
    assert "input_hash" in text


def test_spec_declares_idempotency_rules() -> None:
    text = _read(SPEC)
    assert "Idempotency" in text
    assert "409 idempotency_conflict" in text


def test_expected_schema_files_exist() -> None:
    files = {p.name for p in SCHEMAS_DIR.glob("*.json")}
    assert EXPECTED_SCHEMAS.issubset(files)


def test_schema_files_are_valid_json_and_object_schemas() -> None:
    for filename in EXPECTED_SCHEMAS:
        obj = json.loads(_read(SCHEMAS_DIR / filename))
        assert isinstance(obj, dict)
        assert obj.get("type") == "object"


def test_audit_schema_contains_required_fields() -> None:
    audit = json.loads(_read(SCHEMAS_DIR / "tool_action_audit_event.schema.json"))
    required = set(audit.get("required", []))
    assert {"event_id", "event_type", "timestamp", "tool", "action", "actor", "phase"}.issubset(required)
