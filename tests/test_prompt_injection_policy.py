from __future__ import annotations

import pytest

from app.ai.tool_policy import is_mutation, validate_tool_call


def test_unknown_tool_blocked() -> None:
    with pytest.raises(ValueError, match="tool_not_allowed"):
        validate_tool_call("drop_database", {"query": "x"})


def test_extra_args_rejected() -> None:
    with pytest.raises(ValueError, match="validation_error"):
        validate_tool_call(
            "search_documents",
            {"query": "Angebot", "limit": 10, "__proto__": "inject"},
        )


def test_mutation_requires_confirmation() -> None:
    decision = validate_tool_call(
        "create_task",
        {
            "title": "Follow-up Kunde",
            "details": "Bitte Rueckruf",
            "severity": "INFO",
            "task_type": "GENERAL",
        },
    )
    assert decision.requires_confirm is True
    assert is_mutation(decision.tool_name) is True


def test_read_only_tool_stays_direct() -> None:
    decision = validate_tool_call("search_contacts", {"query": "Mueller", "limit": 5})
    assert decision.requires_confirm is False
    assert is_mutation(decision.tool_name) is False
