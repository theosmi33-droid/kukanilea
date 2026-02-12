from __future__ import annotations

from app.ai import knowledge


def test_ai_knowledge_store_and_search_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge.Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(knowledge, "chromadb", None)
    monkeypatch.setattr(knowledge, "ollama", None)

    knowledge.init_chroma()
    knowledge.store_entity(
        "project",
        10,
        "Sanierung Dach Projekt Berlin",
        {"budget_hours": 120, "actual_hours": 130},
    )
    knowledge.store_entity(
        "task",
        20,
        "Rechnung pruefen und freigeben",
        {"project_id": 10},
    )

    hits = knowledge.find_similar("Dach Berlin", n=5)
    assert hits
    assert {"id", "text", "metadata", "distance"}.issubset(hits[0].keys())
