from __future__ import annotations

from app import create_app
from app.agents import orchestrator


def test_orchestrator_facts_only_when_llm_missing(monkeypatch):
    app = create_app()
    with app.test_request_context("/"):
        monkeypatch.setattr(
            orchestrator.retrieval_fts, "process_queue", lambda limit=200: 0
        )
        monkeypatch.setattr(
            orchestrator.retrieval_fts,
            "search",
            lambda query, limit=6: [
                {
                    "text": "Task #1 offen",
                    "meta": {"kind": "task", "pk": 1},
                    "score": 0.0,
                }
            ],
        )
        monkeypatch.setattr(orchestrator.llm_ollama, "generate", lambda prompt: None)
        out = orchestrator.answer("zeige tasks")

    assert set(out.keys()) == {"text", "facts", "action"}
    assert out["action"] is None
    assert out["facts"]


def test_orchestrator_dispatches_action(monkeypatch):
    app = create_app()
    with app.test_request_context("/"):
        monkeypatch.setattr(
            orchestrator.retrieval_fts, "process_queue", lambda limit=200: 0
        )
        monkeypatch.setattr(
            orchestrator.retrieval_fts, "search", lambda query, limit=6: []
        )
        monkeypatch.setattr(
            orchestrator.llm_ollama,
            "generate",
            lambda prompt: '{"action":"create_task","args":{"title":"A"}}',
        )
        monkeypatch.setattr(
            orchestrator.tools,
            "dispatch",
            lambda *a, **k: {"result": {"task_id": 7}, "error": None},
        )
        out = orchestrator.answer("lege task an")

    assert set(out.keys()) == {"text", "facts", "action"}
    assert out["action"]["name"] == "create_task"
    assert out["action"]["result"]["task_id"] == 7
