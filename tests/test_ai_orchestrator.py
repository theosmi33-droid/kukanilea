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


def test_ai_orchestrator_memory_command_works_without_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orchestrator, "add_user_note", lambda **kwargs: "note-1")
    monkeypatch.setattr(
        orchestrator, "save_conversation", lambda **kwargs: "conv-memory"
    )
    monkeypatch.setattr(orchestrator, "event_append", lambda **kwargs: 1)

    out = orchestrator.process_message(
        tenant_id="TENANT_A",
        user_id="dev",
        user_message="Merke dir: Kunde bevorzugt WhatsApp.",
        read_only=False,
    )
    assert out["status"] == "ok"
    assert out["provider"] == "local_memory"
    assert out["conversation_id"] == "conv-memory"
    assert out["tool_used"] == ["personal_memory.save"]


def test_ai_orchestrator_includes_personal_memory_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orchestrator, "ollama_is_available", lambda **kwargs: True)
    monkeypatch.setattr(orchestrator, "list_recent_conversations", lambda **kwargs: [])
    monkeypatch.setattr(
        orchestrator,
        "render_user_memory_context",
        lambda **kwargs: "Persoenliche Notizen dieses Nutzers:\\n- bevorzugt kurze Antworten",
    )
    captured_messages: dict[str, object] = {}

    def _fake_run(fn, **kwargs):  # noqa: ANN001
        captured_messages["messages"] = kwargs.get("messages")
        return {"message": {"content": "ok"}}

    monkeypatch.setattr(orchestrator.llm_queue, "run", _fake_run)
    monkeypatch.setattr(orchestrator, "save_conversation", lambda **kwargs: "conv-ctx")
    monkeypatch.setattr(orchestrator, "event_append", lambda **kwargs: 1)

    out = orchestrator.process_message(
        tenant_id="TENANT_A",
        user_id="dev",
        user_message="Was ist der Status?",
        read_only=False,
    )
    assert out["status"] == "ok"
    msgs = captured_messages.get("messages")
    assert isinstance(msgs, list)
    assert any(
        "Persoenliche Notizen dieses Nutzers" in str(row.get("content", ""))
        for row in msgs
        if isinstance(row, dict)
    )
