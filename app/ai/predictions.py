from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from flask import current_app, has_app_context

from app.config import Config

from .knowledge import find_similar


def _core_db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["CORE_DB"])
    return Path(Config.CORE_DB)


def _connect() -> sqlite3.Connection:
    db = _core_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    return con


def _ensure_ai_tables(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_predictions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tenant_id TEXT,
          project_id INTEGER NOT NULL,
          predicted_hours REAL,
          predicted_cost REAL,
          deviation_ratio REAL,
          llm_summary TEXT,
          meta_json TEXT,
          created_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_insights(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tenant_id TEXT,
          project_id INTEGER,
          insight_type TEXT NOT NULL,
          title TEXT NOT NULL,
          message TEXT NOT NULL,
          meta_json TEXT,
          created_at TEXT NOT NULL
        )
        """
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _llm_budget_summary(payload: dict[str, Any]) -> str:
    host = "http://127.0.0.1:11434"
    model = "phi3:instruct"
    if has_app_context():
        host = str(current_app.config.get("OLLAMA_HOST", host)).rstrip("/")
        model = str(current_app.config.get("OLLAMA_MODEL", model))

    prompt = (
        "Erstelle eine kurze Budget-Risikoanalyse auf Deutsch (2 Saetze).\n"
        f"Daten: {json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        resp = requests.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        text = str(data.get("response") or "").strip()
        if text:
            return text
    except Exception:
        pass
    return "KI-Analyse offline: Prognose basiert auf lokalen Vergleichsprojekten."


def predict_budget(project_id: int, tenant_id: str = "") -> dict[str, Any]:
    """Predict budget trajectory for a project using similar projects + optional LLM summary."""
    project_id = int(project_id)
    if project_id <= 0:
        raise ValueError("project_id_required")

    con = _connect()
    try:
        _ensure_ai_tables(con)
        row = con.execute(
            """
            SELECT id, tenant_id, name, description, budget_hours, budget_cost
            FROM time_projects
            WHERE id=?
            """,
            (project_id,),
        ).fetchone()
        if not row:
            raise ValueError("project_not_found")

        tenant = str(row["tenant_id"] or tenant_id or "")
        totals = con.execute(
            """
            SELECT COALESCE(SUM(duration_seconds), 0) AS total_seconds
            FROM time_entries
            WHERE project_id=? AND tenant_id=?
            """,
            (project_id, tenant),
        ).fetchone()

        actual_hours = float((totals["total_seconds"] or 0) / 3600.0) if totals else 0.0
        budget_hours = float(row["budget_hours"] or 0)
        budget_cost = float(row["budget_cost"] or 0.0)

        query = f"{row['name']} {row['description'] or ''}".strip()
        similar = find_similar(query, n=5)

        deviations: list[float] = []
        for item in similar:
            md = item.get("metadata") or {}
            if not isinstance(md, dict):
                continue
            bh = float(md.get("budget_hours") or 0.0)
            ah = float(md.get("actual_hours") or 0.0)
            if bh > 0:
                deviations.append((ah - bh) / bh)

        deviation_ratio = (sum(deviations) / len(deviations)) if deviations else 0.0
        predicted_hours = (
            max(0.0, budget_hours * (1.0 + deviation_ratio))
            if budget_hours > 0
            else actual_hours
        )
        predicted_cost = (
            max(0.0, budget_cost * (1.0 + deviation_ratio)) if budget_cost > 0 else 0.0
        )

        llm_payload = {
            "project_id": project_id,
            "name": row["name"],
            "actual_hours": round(actual_hours, 2),
            "budget_hours": round(budget_hours, 2),
            "predicted_hours": round(predicted_hours, 2),
            "deviation_ratio": round(deviation_ratio, 4),
            "similar_count": len(similar),
        }
        llm_summary = _llm_budget_summary(llm_payload)

        con.execute(
            """
            INSERT INTO ai_predictions(
              tenant_id, project_id, predicted_hours, predicted_cost, deviation_ratio,
              llm_summary, meta_json, created_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                tenant,
                project_id,
                float(predicted_hours),
                float(predicted_cost),
                float(deviation_ratio),
                llm_summary,
                json.dumps({"similar": similar[:5]}, ensure_ascii=False),
                _now_iso(),
            ),
        )
        con.commit()

        return {
            "project_id": project_id,
            "tenant_id": tenant,
            "actual_hours": round(actual_hours, 2),
            "budget_hours": round(budget_hours, 2),
            "budget_cost": round(budget_cost, 2),
            "predicted_hours": round(predicted_hours, 2),
            "predicted_cost": round(predicted_cost, 2),
            "deviation_ratio": round(deviation_ratio, 4),
            "summary": llm_summary,
            "similar_count": len(similar),
        }
    finally:
        con.close()


def daily_report(tenant_id: str = "") -> dict[str, Any]:
    """Run prediction for active projects and persist insights."""
    con = _connect()
    try:
        _ensure_ai_tables(con)
        if tenant_id:
            rows = con.execute(
                "SELECT id, tenant_id, name FROM time_projects WHERE status='ACTIVE' AND tenant_id=? ORDER BY id",
                (tenant_id,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT id, tenant_id, name FROM time_projects WHERE status='ACTIVE' ORDER BY id"
            ).fetchall()

        processed = 0
        warnings = 0
        for row in rows:
            pred = predict_budget(int(row["id"]), tenant_id=str(row["tenant_id"] or ""))
            ratio = float(pred.get("deviation_ratio") or 0.0)
            level = "warning" if ratio >= 0.2 else "info"
            if level == "warning":
                warnings += 1
            title = f"Budget-Prognose Projekt {row['name']}"
            msg = (
                f"Prognose: {pred['predicted_hours']}h bei Budget {pred['budget_hours']}h "
                f"(Abweichung {round(ratio * 100, 1)}%)."
            )
            con.execute(
                """
                INSERT INTO ai_insights(tenant_id, project_id, insight_type, title, message, meta_json, created_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    str(row["tenant_id"] or ""),
                    int(row["id"]),
                    level,
                    title,
                    msg,
                    json.dumps(pred, ensure_ascii=False),
                    _now_iso(),
                ),
            )
            processed += 1

        con.commit()
        return {"processed": processed, "warnings": warnings}
    finally:
        con.close()
