from __future__ import annotations

from typing import Any, TypedDict


class AutomationComponentInput(TypedDict, total=False):
    id: str
    type: str
    trigger_type: str
    condition_type: str
    action_type: str
    config: Any
    config_json: str


class AutomationComponent(TypedDict):
    id: str
    tenant_id: str
    rule_id: str
    type: str
    config: Any
    created_at: str
    updated_at: str


class AutomationRuleSummary(TypedDict):
    id: str
    tenant_id: str
    name: str
    description: str
    is_enabled: bool
    version: int
    created_at: str
    updated_at: str
    trigger_count: int
    condition_count: int
    action_count: int


class AutomationRuleRecord(TypedDict):
    id: str
    tenant_id: str
    name: str
    description: str
    is_enabled: bool
    version: int
    created_at: str
    updated_at: str
    triggers: list[AutomationComponent]
    conditions: list[AutomationComponent]
    actions: list[AutomationComponent]
