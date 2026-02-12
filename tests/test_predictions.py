from __future__ import annotations

import sqlite3

from app.ai import predictions


class _FailResp:
    def raise_for_status(self):
        raise RuntimeError("offline")


def _seed_core_db(path):
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            """
            CREATE TABLE time_projects(
              id INTEGER PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              name TEXT NOT NULL,
              description TEXT,
              status TEXT NOT NULL,
              budget_hours INTEGER,
              budget_cost REAL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE time_entries(
              id INTEGER PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              project_id INTEGER,
              duration_seconds INTEGER,
              duration INTEGER
            )
            """
        )
        con.execute(
            "INSERT INTO time_projects(id, tenant_id, name, description, status, budget_hours, budget_cost) VALUES (1,'TENANT1','Projekt A','Beschreibung','ACTIVE',10,1000.0)"
        )
        con.execute(
            "INSERT INTO time_entries(id, tenant_id, project_id, duration_seconds, duration) VALUES (1,'TENANT1',1,7200,7200)"
        )
        con.commit()
    finally:
        con.close()


def test_predict_budget_with_similarity(tmp_path, monkeypatch):
    core_db = tmp_path / "core.sqlite3"
    _seed_core_db(core_db)

    monkeypatch.setattr(predictions.Config, "CORE_DB", core_db)
    monkeypatch.setattr(
        predictions,
        "find_similar",
        lambda query, n=5: [
            {"metadata": {"budget_hours": 10, "actual_hours": 12}},
            {"metadata": {"budget_hours": 8, "actual_hours": 9}},
        ],
    )
    monkeypatch.setattr(predictions.requests, "post", lambda *a, **k: _FailResp())

    out = predictions.predict_budget(1, tenant_id="TENANT1")
    assert out["project_id"] == 1
    assert out["predicted_hours"] > 0
    assert "summary" in out

    con = sqlite3.connect(str(core_db))
    try:
        row = con.execute("SELECT COUNT(*) FROM ai_predictions").fetchone()
        assert int(row[0]) >= 1
    finally:
        con.close()


def test_daily_report_creates_insights(tmp_path, monkeypatch):
    core_db = tmp_path / "core.sqlite3"
    _seed_core_db(core_db)

    monkeypatch.setattr(predictions.Config, "CORE_DB", core_db)
    monkeypatch.setattr(predictions.requests, "post", lambda *a, **k: _FailResp())
    monkeypatch.setattr(
        predictions,
        "find_similar",
        lambda query, n=5: [{"metadata": {"budget_hours": 10, "actual_hours": 14}}],
    )

    result = predictions.daily_report(tenant_id="TENANT1")
    assert result["processed"] >= 1

    con = sqlite3.connect(str(core_db))
    try:
        row = con.execute("SELECT COUNT(*) FROM ai_insights").fetchone()
        assert int(row[0]) >= 1
    finally:
        con.close()
