from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.base import AgentContext
from app.agents.orchestrator import Orchestrator
from app.agents.policy import PolicyEngine


@pytest.mark.parametrize("role", ["OPERATOR", "ADMIN", "DEV"])
def test_policy_allows_mail_actions_for_mail_agent_roles(role: str):
    policy = PolicyEngine()

    assert policy.policy_check(role, "KUKANILEA", "mail_generate", "mail") is True
    assert policy.policy_check(role, "KUKANILEA", "mail_send", "mail") is True


def test_orchestrator_keeps_mail_send_action_for_operator_role():
    core = SimpleNamespace(DB_PATH=":memory:")
    llm = SimpleNamespace(rewrite_query=lambda _message: {})
    orchestrator = Orchestrator(core_module=core, llm_provider=llm)
    context = AgentContext(tenant_id="KUKANILEA", user="operator", role="OPERATOR")

    result = orchestrator.handle("Bitte schick die Mail an den Kunden", context)

    assert result.intent == "mail"
    assert result.actions == [
        {
            "type": "mail_send",
            "confirm_required": True,
            "target": "customer",
            "reason": "user_request",
            "attachments": [],
        }
    ]
