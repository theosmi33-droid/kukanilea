from __future__ import annotations

import pytest

from app.ai import orchestrator


def test_ai_orchestrator_fail_closed_when_ollama_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orchestrator, "ollama_is_available", lambda **kwargs: False)

    out = orchestrator.process_message(
        tenant_id="TENANT_A",
        user_id="dev",
        user_message="hallo",
        read_only=False,
    )
    assert out["status"] == "ai_disabled"
    assert out["conversation_id"] is None


def test_ai_orchestrator_tool_call_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "ollama_is_available", lambda **kwargs: True)
    monkeypatch.setattr(
        orchestrator,
        "list_recent_conversations",
        lambda tenant_id, user_id, limit=3: [],
    )

    responses = iter(
        [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "search_contacts",
                                "arguments": {"query": "Mueller"},
                            }
                        }
                    ],
                }
            },
            {"message": {"content": "Ich habe Kontakte gefunden."}},
        ]
    )

    monkeypatch.setattr(
        orchestrator.llm_queue, "run", lambda fn, **kwargs: next(responses)
    )
    monkeypatch.setattr(
        orchestrator,
        "execute_tool",
        lambda **kwargs: {"result": {"count": 1, "contacts": []}, "error": None},
    )
    monkeypatch.setattr(orchestrator, "save_conversation", lambda **kwargs: "conv-1")
    monkeypatch.setattr(orchestrator, "event_append", lambda **kwargs: 1)

    out = orchestrator.process_message(
        tenant_id="TENANT_A",
        user_id="dev",
        user_message="Suche Mueller",
        read_only=False,
    )
    assert out["status"] == "ok"
    assert out["conversation_id"] == "conv-1"
    assert out["tool_used"] == ["search_contacts"]
    assert "gefunden" in out["response"].lower()
