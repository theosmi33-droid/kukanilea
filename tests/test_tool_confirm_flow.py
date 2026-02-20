from __future__ import annotations

from pathlib import Path

import pytest

from app.ai import confirm, orchestrator
from app.config import Config


def test_confirmation_token_roundtrip_and_replay(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "SECRET_KEY", "test-secret")

    token = confirm.sign_confirmation(
        tenant_id="TENANT_A",
        user_id="dev",
        tool_name="create_task",
        args={"title": "Task"},
        ttl_seconds=300,
    )
    payload = confirm.verify_confirmation(
        token=token,
        tenant_id="TENANT_A",
        user_id="dev",
        consume=True,
    )
    assert payload["tool_name"] == "create_task"

    with pytest.raises(ValueError, match="token_replayed"):
        confirm.verify_confirmation(
            token=token,
            tenant_id="TENANT_A",
            user_id="dev",
            consume=True,
        )


def test_confirmation_token_rejects_tenant_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "SECRET_KEY", "test-secret")

    token = confirm.sign_confirmation(
        tenant_id="TENANT_A",
        user_id="dev",
        tool_name="create_task",
        args={"title": "Task"},
        ttl_seconds=300,
    )
    with pytest.raises(ValueError, match="tenant_mismatch"):
        confirm.verify_confirmation(
            token=token,
            tenant_id="TENANT_B",
            user_id="dev",
            consume=True,
        )


def test_ai_orchestrator_returns_confirmation_for_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orchestrator, "ollama_is_available", lambda **kwargs: True)
    monkeypatch.setattr(
        orchestrator,
        "list_recent_conversations",
        lambda tenant_id, user_id, limit=3: [],
    )
    monkeypatch.setattr(
        orchestrator.llm_queue,
        "run",
        lambda fn, **kwargs: {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "create_task",
                            "arguments": {"title": "Meeting vorbereiten"},
                        }
                    }
                ],
            }
        },
    )
    monkeypatch.setattr(orchestrator, "save_conversation", lambda **kwargs: "conv-2")
    monkeypatch.setattr(orchestrator, "event_append", lambda **kwargs: 1)

    executed = {"called": False}

    def _execute_tool(**kwargs):
        executed["called"] = True
        return {"result": {}, "error": None}

    monkeypatch.setattr(orchestrator, "execute_tool", _execute_tool)

    out = orchestrator.process_message(
        tenant_id="TENANT_A",
        user_id="dev",
        user_message="Erstelle Task",
        read_only=False,
    )

    assert out["status"] == "confirmation_required"
    assert isinstance(out.get("pending_confirmation"), dict)
    assert out["pending_confirmation"]["tool_name"] == "create_task"
    assert executed["called"] is False


def test_confirm_tool_call_executes_after_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        orchestrator,
        "verify_confirmation",
        lambda **kwargs: {
            "tool_name": "create_task",
            "args": {"title": "Meeting vorbereiten"},
        },
    )
    monkeypatch.setattr(
        orchestrator,
        "execute_tool",
        lambda **kwargs: {"result": {"task_id": 101}, "error": None},
    )
    monkeypatch.setattr(orchestrator, "save_conversation", lambda **kwargs: "conv-3")
    monkeypatch.setattr(orchestrator, "event_append", lambda **kwargs: 1)

    out = orchestrator.confirm_tool_call(
        tenant_id="TENANT_A",
        user_id="dev",
        confirmation_token="token",
        read_only=False,
    )

    assert out["status"] == "ok"
    assert out["tool_used"] == ["create_task"]
    assert out["result"] == {"task_id": 101}
