from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional


class ProjectManager:
    def __init__(self, db_extension: Any) -> None:
        self.db = db_extension

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat()

    def create_project(self, tenant: str, name: str, description: str = "") -> int:
        now = self._now_iso()
        con = self.db._db()
        try:
            cur = con.execute(
                """
                INSERT INTO projects(tenant_id, name, description, status, created_at, updated_at)
                VALUES (?,?,?,?,?,?)
                """,
                (tenant, name, description, "ACTIVE", now, now),
            )
            con.commit()
            return int(cur.lastrowid or 0)
        finally:
            con.close()

    def list_projects(self, tenant: str) -> List[Dict[str, Any]]:
        con = self.db._db()
        try:
            rows = con.execute(
                "SELECT * FROM projects WHERE tenant_id=? ORDER BY name",
                (tenant,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def create_task(self, tenant: str, project_id: int, title: str, description: str = "") -> int:
        now = self._now_iso()
        con = self.db._db()
        try:
            cur = con.execute(
                """
                INSERT INTO team_tasks(tenant_id, project_id, title, description, status, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (tenant, project_id, title, description, "OPEN", now, now),
            )
            con.commit()
            return int(cur.lastrowid or 0)
        finally:
            con.close()
