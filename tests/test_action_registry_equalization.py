import pytest
from app.tools.action_registry import ActionRegistry, ActionDefinition
from app.tools.base_tool import BaseTool


class MockTool(BaseTool):
    name = "mock"
    domain = "mock_domain"
    entities = ["entity1", "entity2"]


def test_registry_metadata_completeness():
    registry = ActionRegistry()
    tool = MockTool()
    registry.register_tool(tool)
    
    actions = registry.list_actions()
    assert len(actions) > 0
    for action in actions:
        assert "action_id" in action
        assert "domain" in action
        assert "entity" in action
        assert "verb" in action
        assert "tool" in action
        assert "parameter_schema" in action
        assert "confirm_required" in action
        assert "audit_required" in action
        assert "risk" in action
        assert "external_call" in action
        assert "idempotency" in action


def test_duplicate_detection():
    registry = ActionRegistry()
    tool = MockTool()
    registry.register_tool(tool)
    
    with pytest.raises(ValueError, match="Duplicate action_id detected"):
        registry.register_tool(tool)


def test_write_action_enforcement():
    registry = ActionRegistry()
    
    class BadTool(BaseTool):
        name = "bad"
        def actions(self):
            yield {
                "name": "bad.create",
                "verb": "create",
                "confirm_required": False, # Violation
                "audit_required": True
            }
            
    tool = BadTool()
    with pytest.raises(ValueError, match="must have confirm_required and audit_required set to True"):
        registry.register_tool(tool)


def test_registry_stats():
    registry = ActionRegistry()
    tool = MockTool()
    registry.register_tool(tool)
    
    summary = registry.tools_summary()
    assert "mock" in summary
    assert summary["mock"] > 0
    assert registry.count() == summary["mock"]
