from __future__ import annotations

import hashlib
import json
import math
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from flask import has_request_context, session

from app.ai.embeddings import generate_embedding

DEFAULT_COLUMN_SPECS = (
    {"name": "To Do", "color": "#2563eb"},
    {"name": "Doing", "color": "#f59e0b"},
    {"name": "Done", "color": "#16a34a"},
)

ROLE_ORDER = ["READONLY", "MITARBEITER", "MANAGER", "ADMIN", "DEV"]
STATUS_TO_COLUMN = {
    "OPEN": "To Do",
    "IN_PROGRESS": "Doing",
    "DONE": "Done",
    "REJECTED": "Rejected",
}
COLUMN_TO_STATUS = {value: key for key, value in STATUS_TO_COLUMN.items()}
VALID_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


class ProjectManager:
    """Project Hub domain logic for projects, boards, columns and cards."""

    def __init__(self, db_ext):
        self.db = db_ext
        self._ensure_project_schema()
        self._ensure_team_task_schema()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure_project_schema(self) -> None:
        """Create/upgrade Project Hub tables required by route and board flows."""
        con = self.db._db()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS project_boards(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  project_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  description TEXT,
                  archived INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_boards_project ON project_boards(project_id, tenant_id, created_at);"
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS project_columns(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  board_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  position INTEGER NOT NULL DEFAULT 0,
                  color TEXT,
                  archived INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_columns_board ON project_columns(board_id, tenant_id, archived, position);"
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS project_cards(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  board_id TEXT NOT NULL,
                  column_id TEXT NOT NULL,
                  title TEXT NOT NULL,
                  description TEXT,
                  due_date TEXT,
                  assignee TEXT,
                  linked_task_id INTEGER,
                  status TEXT NOT NULL DEFAULT 'OPEN',
                  position INTEGER NOT NULL DEFAULT 0,
                  archived INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_cards_board ON project_cards(board_id, tenant_id, archived, column_id, position);"
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS card_comments(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  card_id TEXT NOT NULL,
                  author TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_card_comments_card ON card_comments(card_id, tenant_id, created_at);"
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS card_attachments(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  card_id TEXT NOT NULL,
                  file_name TEXT NOT NULL,
                  file_path TEXT NOT NULL,
                  uploaded_by TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_card_attachments_card ON card_attachments(card_id, tenant_id, created_at);"
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS card_activities(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  board_id TEXT,
                  card_id TEXT,
                  action TEXT NOT NULL,
                  payload_json TEXT,
                  actor TEXT,
                  created_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_card_activities_board ON card_activities(board_id, tenant_id, created_at);"
            )
            con.commit()
        finally:
            con.close()

    def _ensure_team_task_schema(self) -> None:
        con = self.db._db()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS team_tasks(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  board_id TEXT,
                  title TEXT NOT NULL,
                  description TEXT,
                  priority TEXT NOT NULL DEFAULT 'MEDIUM',
                  due_at TEXT,
                  status TEXT NOT NULL DEFAULT 'OPEN',
                  created_by TEXT NOT NULL,
                  assigned_to TEXT,
                  rejection_reason TEXT,
                  source_type TEXT,
                  source_ref TEXT,
                  parent_task_id TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_team_tasks_tenant ON team_tasks(tenant_id, status, due_at);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS team_task_attachments(
                  id TEXT PRIMARY KEY,
                  task_id TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  value TEXT NOT NULL,
                  scan_status TEXT,
                  metadata_json TEXT,
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(task_id) REFERENCES team_tasks(id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS team_task_events(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  ts TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  action TEXT NOT NULL,
                  reason TEXT,
                  from_user TEXT,
                  to_user TEXT,
                  meta_json TEXT
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_team_task_events_task ON team_task_events(task_id, id DESC);"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS team_task_notifications(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id TEXT NOT NULL,
                  username TEXT NOT NULL,
                  task_id TEXT,
                  kind TEXT NOT NULL,
                  message TEXT NOT NULL,
                  is_read INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_team_task_notifications_user ON team_task_notifications(tenant_id, username, is_read, id DESC);"
            )
            con.commit()
        finally:
            con.close()

    def _context_identity(self) -> tuple[str, str, str]:
        if not has_request_context():
            return "system", "ADMIN", "SYSTEM"
        actor = str(session.get("user") or "anonymous")
        role = str(session.get("role") or "READONLY").upper()
        tenant = str(session.get("tenant_id") or "KUKANILEA")
        normalized_role = self._normalize_role(role)
        return actor, normalized_role, tenant

    @staticmethod
    def _normalize_role(role: str) -> str:
        role_up = str(role or "").upper()
        if role_up in {"ADMIN", "DEV"}:
            return "ADMIN"
        if role_up in {"MANAGER", "OPERATOR"}:
            return "MANAGER"
        if role_up in {"MITARBEITER"}:
            return "MITARBEITER"
        if role_up in {"READONLY"}:
            return "READONLY"
        return "READONLY"

    def _role_allows(self, role: str, required: str) -> bool:
        role_norm = self._normalize_role(role)
        required_norm = self._normalize_role(required)
        return ROLE_ORDER.index(role_norm) >= ROLE_ORDER.index(required_norm)

    def _audit_activity(
        self, con, *, tenant_id: str, username: str, action: str, resource: str, details: str
    ) -> None:
        con.execute(
            "INSERT INTO audit_log(ts, tenant_id, username, action, resource, details) VALUES (?,?,?,?,?,?)",
            (self._now_iso(), tenant_id, username, action, resource, details),
        )

    def _log_task_event(
        self,
        con,
        *,
        task_id: str,
        tenant_id: str,
        actor: str,
        action: str,
        reason: str = "",
        from_user: str = "",
        to_user: str = "",
        meta: dict[str, Any] | None = None,
    ) -> None:
        con.execute(
            """
            INSERT INTO team_task_events(task_id, tenant_id, ts, actor, action, reason, from_user, to_user, meta_json)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                task_id,
                tenant_id,
                self._now_iso(),
                actor,
                action,
                reason or None,
                from_user or None,
                to_user or None,
                json.dumps(meta or {}, ensure_ascii=False),
            ),
        )

    def _notify(
        self,
        con,
        *,
        tenant_id: str,
        username: str,
        task_id: str,
        kind: str,
        message: str,
    ) -> None:
        if not username:
            return
        con.execute(
            """
            INSERT INTO team_task_notifications(tenant_id, username, task_id, kind, message, is_read, created_at)
            VALUES (?,?,?,?,?,0,?)
            """,
            (tenant_id, username, task_id, kind, message[:500], self._now_iso()),
        )

    def _user_exists(self, con, tenant_id: str, username: str) -> bool:
        if not username:
            return False
        row = con.execute(
            "SELECT 1 FROM memberships WHERE tenant_id=? AND username=? LIMIT 1",
            (tenant_id, username),
        ).fetchone()
        return bool(row)

    @staticmethod
    def _normalize_priority(priority: str) -> str:
        value = str(priority or "MEDIUM").strip().upper()
        return value if value in VALID_PRIORITIES else "MEDIUM"

    def _create_attachment(
        self,
        con,
        *,
        task_id: str,
        tenant_id: str,
        created_by: str,
        kind: str,
        value: str,
    ) -> None:
        payload_value = str(value or "").strip()
        if not payload_value:
            return
        kind_norm = str(kind or "LINK").strip().upper()
        metadata: dict[str, Any] = {}
        scan_status = None
        if kind_norm == "UPLOAD":
            from app.core.upload_pipeline import process_upload

            ok, result = process_upload(Path(payload_value), tenant_id)
            if not ok:
                raise ValueError(f"attachment_scan_failed:{result}")
            scan_status = "CLEAN"
            metadata["file_hash"] = result
        con.execute(
            """
            INSERT INTO team_task_attachments(id, task_id, tenant_id, kind, value, scan_status, metadata_json, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                task_id,
                tenant_id,
                kind_norm,
                payload_value,
                scan_status,
                json.dumps(metadata, ensure_ascii=False),
                created_by,
                self._now_iso(),
            ),
        )

    def create_team_task(
        self,
        *,
        tenant_id: str,
        actor: str,
        actor_role: str,
        title: str,
        description: str = "",
        priority: str = "MEDIUM",
        due_at: str = "",
        assigned_to: str = "",
        board_id: str | None = None,
        source_type: str = "",
        source_ref: str = "",
        attachment_link: str = "",
        attachment_upload_path: str = "",
    ) -> str:
        title = str(title or "").strip()
        if not title:
            raise ValueError("title_required")

        con = self.db._db()
        try:
            assignee = str(assigned_to or actor).strip()
            if not self._user_exists(con, tenant_id, assignee):
                raise ValueError("assignee_not_registered")
            if assignee != actor and not self._role_allows(actor_role, "MANAGER"):
                raise PermissionError("assign_requires_manager")

            task_id = str(uuid.uuid4())
            now = self._now_iso()
            con.execute(
                """
                INSERT INTO team_tasks(
                  id, tenant_id, board_id, title, description, priority, due_at, status,
                  created_by, assigned_to, source_type, source_ref, created_at, updated_at
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    task_id,
                    tenant_id,
                    board_id,
                    title[:220],
                    str(description or "")[:5000],
                    self._normalize_priority(priority),
                    str(due_at or "").strip() or None,
                    "OPEN",
                    actor,
                    assignee,
                    str(source_type or "").strip() or None,
                    str(source_ref or "").strip() or None,
                    now,
                    now,
                ),
            )
            if attachment_link:
                self._create_attachment(
                    con,
                    task_id=task_id,
                    tenant_id=tenant_id,
                    created_by=actor,
                    kind="LINK",
                    value=attachment_link,
                )
            if attachment_upload_path:
                self._create_attachment(
                    con,
                    task_id=task_id,
                    tenant_id=tenant_id,
                    created_by=actor,
                    kind="UPLOAD",
                    value=attachment_upload_path,
                )
            self._log_task_event(
                con,
                task_id=task_id,
                tenant_id=tenant_id,
                actor=actor,
                action="TASK_CREATED",
                to_user=assignee,
                meta={"title": title[:220], "priority": self._normalize_priority(priority)},
            )
            self._audit_activity(
                con,
                tenant_id=tenant_id,
                username=actor,
                action="TASK_CREATED",
                resource=f"team_task:{task_id}",
                details=f"created and assigned to {assignee}",
            )
            self._notify(
                con,
                tenant_id=tenant_id,
                username=assignee,
                task_id=task_id,
                kind="TASK_ASSIGNED",
                message=f"Neue Aufgabe: {title[:120]}",
            )
            con.commit()
            return task_id
        finally:
            con.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _fallback_embedding(self, text: str, size: int = 64) -> List[float]:
        vec = [0.0] * size
        for token in (text or "").lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = digest[0] % size
            sign = -1.0 if digest[1] % 2 else 1.0
            weight = 0.4 + (digest[2] / 255.0)
            vec[idx] += sign * weight
        norm = math.sqrt(sum(v * v for v in vec))
        if norm <= 0.0:
            vec[0] = 1.0
            norm = 1.0
        return [v / norm for v in vec]

    def _embed(self, text: str) -> List[float]:
        emb = generate_embedding(text)
        if emb:
            return [float(v) for v in emb]
        return self._fallback_embedding(text)

    def _store_memory(
        self,
        con,
        tenant_id: str,
        actor: str,
        category: str,
        content: str,
        metadata: Dict[str, Any],
        importance: int = 7,
    ) -> None:
        embedding = self._embed(content)
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        con.execute(
            """
            INSERT INTO agent_memory (tenant_id, timestamp, agent_role, content, embedding, metadata, importance_score, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                self._now(),
                actor or "project_hub",
                content,
                blob,
                json.dumps(metadata, ensure_ascii=True),
                max(1, min(int(importance), 10)),
                category,
            ),
        )

    def _log_activity(
        self,
        con,
        *,
        tenant_id: str,
        actor: str,
        action: str,
        resource: str,
        details: str,
        board_id: Optional[str] = None,
        card_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        importance: int = 7,
    ) -> None:
        ts = self._now()
        payload_obj = payload or {}
        con.execute(
            "INSERT INTO audit_log(ts, tenant_id, username, action, resource, details) VALUES (?,?,?,?,?,?)",
            (ts, tenant_id, actor or "system", action, resource, details),
        )
        con.execute(
            """
            INSERT INTO card_activities(id, tenant_id, board_id, card_id, action, payload_json, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                tenant_id,
                board_id,
                card_id,
                action,
                json.dumps(payload_obj, ensure_ascii=True),
                actor or "system",
                ts,
            ),
        )
        memory_text = f"Project Hub activity: {action}. {details}"
        memory_meta = {
            "event_type": "project_hub_activity",
            "action": action,
            "resource": resource,
            "board_id": board_id,
            "card_id": card_id,
            "actor": actor,
            "details": details,
            **payload_obj,
        }
        self._store_memory(
            con,
            tenant_id=tenant_id,
            actor="project_hub",
            category="KANBAN_ACTIVITY",
            content=memory_text,
            metadata=memory_meta,
            importance=importance,
        )

    def _project_row(self, con, tenant_id: str, project_id: str):
        return con.execute(
            "SELECT * FROM projects WHERE id = ? AND tenant_id = ?",
            (project_id, tenant_id),
        ).fetchone()

    def _board_row(self, con, tenant_id: str, board_id: str):
        return con.execute(
            "SELECT * FROM project_boards WHERE id = ? AND tenant_id = ?",
            (board_id, tenant_id),
        ).fetchone()

    def ensure_default_hub(self, tenant_id: str, actor: str = "system") -> Dict[str, Any]:
        if not tenant_id:
            raise ValueError("tenant_required")

        con = self.db._db()
        try:
            project = con.execute(
                "SELECT * FROM projects WHERE tenant_id = ? ORDER BY created_at ASC LIMIT 1",
                (tenant_id,),
            ).fetchone()
            if not project:
                pid = str(uuid.uuid4())
                con.execute(
                    "INSERT INTO projects(id, tenant_id, name, description, created_at) VALUES (?,?,?,?,?)",
                    (
                        pid,
                        tenant_id,
                        "Project Hub",
                        "Lokales Kanban-Board mit Aktivitaetsverlauf.",
                        self._now(),
                    ),
                )
                project = con.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()

            board = con.execute(
                "SELECT * FROM project_boards WHERE tenant_id = ? AND project_id = ? ORDER BY created_at ASC LIMIT 1",
                (tenant_id, project["id"]),
            ).fetchone()
            if not board:
                board_id = str(uuid.uuid4())
                con.execute(
                    """
                    INSERT INTO project_boards(id, tenant_id, project_id, name, description, archived, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        board_id,
                        tenant_id,
                        project["id"],
                        "Main Board",
                        "Standard-Board",
                        self._now(),
                        self._now(),
                    ),
                )
                board = con.execute("SELECT * FROM project_boards WHERE id = ?", (board_id,)).fetchone()

            cols = con.execute(
                "SELECT id FROM project_columns WHERE tenant_id = ? AND board_id = ?",
                (tenant_id, board["id"]),
            ).fetchall()
            if not cols:
                for idx, spec in enumerate(DEFAULT_COLUMN_SPECS):
                    con.execute(
                        """
                        INSERT INTO project_columns(id, tenant_id, board_id, name, position, color, archived, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            tenant_id,
                            board["id"],
                            spec["name"],
                            (idx + 1) * 100,
                            spec["color"],
                            self._now(),
                            self._now(),
                        ),
                    )

            con.commit()
            return {
                "project": dict(project),
                "board": dict(board),
                "columns": self.list_columns(str(board["id"]), tenant_id=tenant_id),
            }
        finally:
            con.close()

    def create_project(self, tenant_id: str, name: str, description: str = "") -> str:
        pid = str(uuid.uuid4())
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO projects(id, tenant_id, name, description, created_at) VALUES (?,?,?,?,?)",
                (pid, tenant_id, (name or "Projekt").strip(), description or "", self._now()),
            )
            con.commit()
            return pid
        finally:
            con.close()

    def create_board(
        self,
        project_id: str,
        name: str,
        *,
        tenant_id: Optional[str] = None,
        description: str = "",
        actor: str = "system",
    ) -> str:
        con = self.db._db()
        try:
            row = con.execute(
                "SELECT tenant_id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                raise ValueError("project_not_found")
            t_id = tenant_id or str(row["tenant_id"])
            if t_id != str(row["tenant_id"]):
                raise PermissionError("tenant_mismatch")

            bid = str(uuid.uuid4())
            now = self._now()
            con.execute(
                """
                INSERT INTO project_boards(id, tenant_id, project_id, name, description, archived, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (bid, t_id, project_id, (name or "Board").strip(), description or "", now, now),
            )
            for idx, spec in enumerate(DEFAULT_COLUMN_SPECS):
                con.execute(
                    """
                    INSERT INTO project_columns(id, tenant_id, board_id, name, position, color, archived, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        t_id,
                        bid,
                        spec["name"],
                        (idx + 1) * 100,
                        spec["color"],
                        now,
                        now,
                    ),
                )
            self._log_activity(
                con,
                tenant_id=t_id,
                actor=actor,
                action="BOARD_CREATED",
                resource=f"board:{bid}",
                details=f"Board '{name}' erstellt.",
                board_id=bid,
                payload={"project_id": project_id, "board_name": name},
                importance=6,
            )
            con.commit()
            return bid
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def list_projects(self, tenant_id: str) -> List[Dict[str, Any]]:
        con = self.db._db()
        try:
            rows = con.execute(
                "SELECT * FROM projects WHERE tenant_id = ? ORDER BY created_at ASC",
                (tenant_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def list_boards(self, tenant_id: str, project_id: str) -> List[Dict[str, Any]]:
        con = self.db._db()
        try:
            rows = con.execute(
                """
                SELECT * FROM project_boards
                WHERE tenant_id = ? AND project_id = ? AND archived = 0
                ORDER BY created_at ASC
                """,
                (tenant_id, project_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def list_columns(self, board_id: str, *, tenant_id: str) -> List[Dict[str, Any]]:
        con = self.db._db()
        try:
            rows = con.execute(
                """
                SELECT * FROM project_columns
                WHERE board_id = ? AND tenant_id = ? AND archived = 0
                ORDER BY position ASC, created_at ASC
                """,
                (board_id, tenant_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def create_column(
        self,
        *,
        tenant_id: str,
        board_id: str,
        name: str,
        color: str = "#64748b",
        actor: str = "system",
    ) -> Dict[str, Any]:
        con = self.db._db()
        try:
            board = self._board_row(con, tenant_id, board_id)
            if not board:
                raise PermissionError("board_not_found_or_forbidden")
            pos_row = con.execute(
                "SELECT COALESCE(MAX(position), 0) AS max_pos FROM project_columns WHERE board_id = ? AND tenant_id = ?",
                (board_id, tenant_id),
            ).fetchone()
            position = int(pos_row["max_pos"] or 0) + 100
            cid = str(uuid.uuid4())
            now = self._now()
            con.execute(
                """
                INSERT INTO project_columns(id, tenant_id, board_id, name, position, color, archived, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (cid, tenant_id, board_id, (name or "Spalte").strip(), position, color or "#64748b", now, now),
            )
            self._log_activity(
                con,
                tenant_id=tenant_id,
                actor=actor,
                action="COLUMN_CREATED",
                resource=f"column:{cid}",
                details=f"Spalte '{name}' erstellt.",
                board_id=board_id,
                payload={"column_id": cid, "column_name": name},
                importance=6,
            )
            con.commit()
            row = con.execute("SELECT * FROM project_columns WHERE id = ?", (cid,)).fetchone()
            return dict(row)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def update_column(
        self,
        *,
        tenant_id: str,
        column_id: str,
        name: Optional[str],
        color: Optional[str],
        position: Optional[int],
        actor: str,
    ) -> Dict[str, Any]:
        con = self.db._db()
        try:
            row = con.execute(
                "SELECT * FROM project_columns WHERE id = ? AND tenant_id = ?",
                (column_id, tenant_id),
            ).fetchone()
            if not row:
                raise PermissionError("column_not_found_or_forbidden")

            next_name = (name or row["name"]).strip()
            next_color = (color or row["color"] or "#64748b").strip()
            next_position = int(position if position is not None else row["position"])
            con.execute(
                "UPDATE project_columns SET name = ?, color = ?, position = ?, updated_at = ? WHERE id = ?",
                (next_name, next_color, next_position, self._now(), column_id),
            )
            self._log_activity(
                con,
                tenant_id=tenant_id,
                actor=actor,
                action="COLUMN_UPDATED",
                resource=f"column:{column_id}",
                details=f"Spalte '{row['name']}' aktualisiert.",
                board_id=row["board_id"],
                payload={"column_id": column_id, "name": next_name, "position": next_position},
                importance=5,
            )
            con.commit()
            new_row = con.execute("SELECT * FROM project_columns WHERE id = ?", (column_id,)).fetchone()
            return dict(new_row)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def delete_column(
        self,
        *,
        tenant_id: str,
        column_id: str,
        fallback_column_id: Optional[str],
        actor: str,
    ) -> None:
        con = self.db._db()
        try:
            column = con.execute(
                "SELECT * FROM project_columns WHERE id = ? AND tenant_id = ?",
                (column_id, tenant_id),
            ).fetchone()
            if not column:
                raise PermissionError("column_not_found_or_forbidden")

            cards_count = con.execute(
                "SELECT COUNT(*) AS c FROM project_cards WHERE tenant_id = ? AND column_id = ?",
                (tenant_id, column_id),
            ).fetchone()["c"]
            if cards_count and not fallback_column_id:
                raise ValueError("fallback_column_required")
            if fallback_column_id:
                target = con.execute(
                    "SELECT id FROM project_columns WHERE id = ? AND tenant_id = ? AND board_id = ?",
                    (fallback_column_id, tenant_id, column["board_id"]),
                ).fetchone()
                if not target:
                    raise ValueError("invalid_fallback_column")
                con.execute(
                    "UPDATE project_cards SET column_id = ?, updated_at = ? WHERE tenant_id = ? AND column_id = ?",
                    (fallback_column_id, self._now(), tenant_id, column_id),
                )

            con.execute(
                "UPDATE project_columns SET archived = 1, updated_at = ? WHERE id = ?",
                (self._now(), column_id),
            )
            self._log_activity(
                con,
                tenant_id=tenant_id,
                actor=actor,
                action="COLUMN_ARCHIVED",
                resource=f"column:{column_id}",
                details=f"Spalte '{column['name']}' archiviert.",
                board_id=column["board_id"],
                payload={"column_id": column_id, "fallback_column_id": fallback_column_id},
                importance=6,
            )
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _assert_column_access(self, con, tenant_id: str, column_id: str) -> sqlite3.Row:
        row = con.execute(
            "SELECT * FROM project_columns WHERE id = ? AND tenant_id = ? AND archived = 0",
            (column_id, tenant_id),
        ).fetchone()
        if not row:
            raise PermissionError("column_not_found_or_forbidden")
        return row

    def create_card(
        self,
        *,
        tenant_id: str,
        board_id: str,
        column_id: str,
        title: str,
        description: str = "",
        due_date: str = "",
        assignee: str = "",
        actor: str = "system",
    ) -> Dict[str, Any]:
        con = self.db._db()
        try:
            board = self._board_row(con, tenant_id, board_id)
            if not board:
                raise PermissionError("board_not_found_or_forbidden")
            column = self._assert_column_access(con, tenant_id, column_id)
            if str(column["board_id"]) != str(board_id):
                raise ValueError("column_not_in_board")

            pos_row = con.execute(
                "SELECT COALESCE(MAX(position), 0) AS max_pos FROM project_cards WHERE tenant_id = ? AND column_id = ?",
                (tenant_id, column_id),
            ).fetchone()
            position = int(pos_row["max_pos"] or 0) + 100
            cid = str(uuid.uuid4())
            now = self._now()
            con.execute(
                """
                INSERT INTO project_cards(
                    id, tenant_id, board_id, column_id, title, description, due_date,
                    assignee, linked_task_id, status, position, archived,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'OPEN', ?, 0, ?, ?)
                """,
                (
                    cid,
                    tenant_id,
                    board_id,
                    column_id,
                    (title or "Neue Karte").strip(),
                    description or "",
                    due_date or None,
                    assignee or "",
                    position,
                    now,
                    now,
                ),
            )
            self._log_activity(
                con,
                tenant_id=tenant_id,
                actor=actor,
                action="CARD_CREATED",
                resource=f"card:{cid}",
                details=f"Karte '{title}' erstellt.",
                board_id=board_id,
                card_id=cid,
                payload={"column_id": column_id, "title": title},
                importance=7,
            )
            con.commit()
            card = con.execute(
                "SELECT * FROM project_cards WHERE id = ? AND tenant_id = ?",
                (cid, tenant_id),
            ).fetchone()
            return dict(card)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def get_card(self, *, tenant_id: str, card_id: str) -> Optional[Dict[str, Any]]:
        con = self.db._db()
        try:
            row = con.execute(
                "SELECT * FROM project_cards WHERE id = ? AND tenant_id = ? AND archived = 0",
                (card_id, tenant_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            con.close()

    def update_card(
        self,
        *,
        tenant_id: str,
        card_id: str,
        actor: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> Dict[str, Any]:
        con = self.db._db()
        try:
            row = con.execute(
                "SELECT * FROM project_cards WHERE id = ? AND tenant_id = ? AND archived = 0",
                (card_id, tenant_id),
            ).fetchone()
            if not row:
                raise PermissionError("card_not_found_or_forbidden")
            next_title = (title if title is not None else row["title"]).strip()
            next_desc = description if description is not None else (row["description"] or "")
            next_due = due_date if due_date is not None else row["due_date"]
            next_assignee = assignee if assignee is not None else (row["assignee"] or "")
            con.execute(
                """
                UPDATE project_cards
                SET title = ?, description = ?, due_date = ?, assignee = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_title, next_desc, next_due, next_assignee, self._now(), card_id),
            )
            self._log_activity(
                con,
                tenant_id=tenant_id,
                actor=actor,
                action="CARD_UPDATED",
                resource=f"card:{card_id}",
                details=f"Karte '{next_title}' aktualisiert.",
                board_id=row["board_id"],
                card_id=card_id,
                payload={"title": next_title, "due_date": next_due, "assignee": next_assignee},
                importance=6,
            )
            con.commit()
            updated = con.execute("SELECT * FROM project_cards WHERE id = ?", (card_id,)).fetchone()
            return dict(updated)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def move_card(
        self,
        *,
        tenant_id: str,
        card_id: str,
        to_column_id: str,
        actor: str,
        reason: str = "",
        position: Optional[int] = None,
    ) -> Dict[str, Any]:
        con = self.db._db()
        try:
            card = con.execute(
                "SELECT * FROM project_cards WHERE id = ? AND tenant_id = ? AND archived = 0",
                (card_id, tenant_id),
            ).fetchone()
            if not card:
                raise PermissionError("card_not_found_or_forbidden")
            new_col = self._assert_column_access(con, tenant_id, to_column_id)
            if str(new_col["board_id"]) != str(card["board_id"]):
                raise ValueError("column_not_in_board")

            target_pos = int(position) if position is not None else int((con.execute(
                "SELECT COALESCE(MAX(position), 0) AS max_pos FROM project_cards WHERE tenant_id = ? AND column_id = ?",
                (tenant_id, to_column_id),
            ).fetchone()["max_pos"] or 0) + 100)
            from_column_id = str(card["column_id"])
            from_col_name = con.execute("SELECT name FROM project_columns WHERE id = ?", (from_column_id,)).fetchone()
            to_col_name = con.execute("SELECT name FROM project_columns WHERE id = ?", (to_column_id,)).fetchone()
            con.execute(
                "UPDATE project_cards SET column_id = ?, position = ?, updated_at = ? WHERE id = ?",
                (to_column_id, target_pos, self._now(), card_id),
            )
            reason_text = (reason or "Keine Begruendung angegeben.").strip()
            detail = (
                f"Karte '{card['title']}' verschoben von '{from_col_name['name'] if from_col_name else from_column_id}' "
                f"nach '{to_col_name['name'] if to_col_name else to_column_id}'. Grund: {reason_text}"
            )
            self._log_activity(
                con,
                tenant_id=tenant_id,
                actor=actor,
                action="CARD_MOVED",
                resource=f"card:{card_id}",
                details=detail,
                board_id=card["board_id"],
                card_id=card_id,
                payload={
                    "from_column_id": from_column_id,
                    "to_column_id": to_column_id,
                    "from_column_name": from_col_name["name"] if from_col_name else from_column_id,
                    "to_column_name": to_col_name["name"] if to_col_name else to_column_id,
                    "reason": reason_text,
                },
                importance=8,
            )
            con.commit()
            updated = con.execute("SELECT * FROM project_cards WHERE id = ?", (card_id,)).fetchone()
            return dict(updated)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def add_comment(self, *, tenant_id: str, card_id: str, author: str, content: str) -> Dict[str, Any]:
        con = self.db._db()
        try:
            card = con.execute(
                "SELECT * FROM project_cards WHERE id = ? AND tenant_id = ? AND archived = 0",
                (card_id, tenant_id),
            ).fetchone()
            if not card:
                raise PermissionError("card_not_found_or_forbidden")
            text = (content or "").strip()
            if not text:
                raise ValueError("comment_empty")
            comment_id = str(uuid.uuid4())
            now = self._now()
            con.execute(
                """
                INSERT INTO card_comments(id, tenant_id, card_id, author, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (comment_id, tenant_id, card_id, author or "system", text, now),
            )
            self._log_activity(
                con,
                tenant_id=tenant_id,
                actor=author or "system",
                action="CARD_COMMENT_ADDED",
                resource=f"card:{card_id}",
                details=f"Kommentar auf Karte '{card['title']}' hinzugefuegt.",
                board_id=card["board_id"],
                card_id=card_id,
                payload={"comment_id": comment_id, "comment": text[:300]},
                importance=7,
            )
            con.commit()
            row = con.execute("SELECT * FROM card_comments WHERE id = ?", (comment_id,)).fetchone()
            return dict(row)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def list_comments(self, *, tenant_id: str, card_id: str) -> List[Dict[str, Any]]:
        con = self.db._db()
        try:
            rows = con.execute(
                """
                SELECT * FROM card_comments
                WHERE tenant_id = ? AND card_id = ?
                ORDER BY created_at ASC
                """,
                (tenant_id, card_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def add_attachment(
        self,
        *,
        tenant_id: str,
        card_id: str,
        actor: str,
        file_path: str,
        file_name: str = "",
    ) -> Dict[str, Any]:
        con = self.db._db()
        try:
            card = con.execute(
                "SELECT * FROM project_cards WHERE id = ? AND tenant_id = ? AND archived = 0",
                (card_id, tenant_id),
            ).fetchone()
            if not card:
                raise PermissionError("card_not_found_or_forbidden")
            path = (file_path or "").strip()
            if not path:
                raise ValueError("file_path_required")
            aid = str(uuid.uuid4())
            now = self._now()
            name = (file_name or "").strip() or path.split("/")[-1]
            con.execute(
                """
                INSERT INTO card_attachments(id, tenant_id, card_id, file_name, file_path, uploaded_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (aid, tenant_id, card_id, name, path, actor or "system", now),
            )
            self._log_activity(
                con,
                tenant_id=tenant_id,
                actor=actor,
                action="CARD_ATTACHMENT_ADDED",
                resource=f"card:{card_id}",
                details=f"Anhang '{name}' zu Karte '{card['title']}' hinzugefuegt.",
                board_id=card["board_id"],
                card_id=card_id,
                payload={"attachment_id": aid, "file_name": name, "file_path": path},
                importance=7,
            )
            con.commit()
            row = con.execute("SELECT * FROM card_attachments WHERE id = ?", (aid,)).fetchone()
            return dict(row)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def list_attachments(self, *, tenant_id: str, card_id: str) -> List[Dict[str, Any]]:
        con = self.db._db()
        try:
            rows = con.execute(
                "SELECT * FROM card_attachments WHERE tenant_id = ? AND card_id = ? ORDER BY created_at DESC",
                (tenant_id, card_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def list_activities(self, *, tenant_id: str, board_id: str, limit: int = 60) -> List[Dict[str, Any]]:
        con = self.db._db()
        try:
            rows = con.execute(
                """
                SELECT * FROM card_activities
                WHERE tenant_id = ? AND board_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (tenant_id, board_id, max(1, min(int(limit), 300))),
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                try:
                    d["payload"] = json.loads(d.get("payload_json") or "{}")
                except Exception:
                    d["payload"] = {}
                out.append(d)
            return out
        finally:
            con.close()

    def list_board_cards(self, *, tenant_id: str, board_id: str) -> List[Dict[str, Any]]:
        con = self.db._db()
        try:
            rows = con.execute(
                """
                SELECT * FROM project_cards
                WHERE tenant_id = ? AND board_id = ? AND archived = 0
                ORDER BY column_id, position ASC, created_at ASC
                """,
                (tenant_id, board_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def list_board_state(self, *, tenant_id: str, board_id: str) -> Dict[str, Any]:
        con = self.db._db()
        try:
            board = self._board_row(con, tenant_id, board_id)
            if not board:
                raise PermissionError("board_not_found_or_forbidden")
            project = self._project_row(con, tenant_id, board["project_id"])
            if not project:
                raise PermissionError("project_not_found_or_forbidden")
            columns = self.list_columns(board_id, tenant_id=tenant_id)
            cards = self.list_board_cards(tenant_id=tenant_id, board_id=board_id)

            comments_count = {
                row["card_id"]: row["c"]
                for row in con.execute(
                    "SELECT card_id, COUNT(*) AS c FROM card_comments WHERE tenant_id = ? GROUP BY card_id",
                    (tenant_id,),
                ).fetchall()
            }
            attachments_count = {
                row["card_id"]: row["c"]
                for row in con.execute(
                    "SELECT card_id, COUNT(*) AS c FROM card_attachments WHERE tenant_id = ? GROUP BY card_id",
                    (tenant_id,),
                ).fetchall()
            }
            for card in cards:
                card["comments_count"] = int(comments_count.get(card["id"], 0))
                card["attachments_count"] = int(attachments_count.get(card["id"], 0))

            return {
                "project": dict(project),
                "board": dict(board),
                "columns": columns,
                "cards": cards,
                "activities": self.list_activities(tenant_id=tenant_id, board_id=board_id, limit=40),
            }
        finally:
            con.close()

    def link_card_task(
        self,
        *,
        tenant_id: str,
        card_id: str,
        actor: str,
        task_id: Optional[int] = None,
        task_creator: Optional[Callable[..., int]] = None,
    ) -> Dict[str, Any]:
        con = self.db._db()
        try:
            card = con.execute(
                "SELECT * FROM project_cards WHERE id = ? AND tenant_id = ? AND archived = 0",
                (card_id, tenant_id),
            ).fetchone()
            if not card:
                raise PermissionError("card_not_found_or_forbidden")

            linked_task_id: Optional[int] = int(task_id) if task_id is not None else None
            if linked_task_id is None and callable(task_creator):
                linked_task_id = int(
                    task_creator(
                        tenant=tenant_id,
                        severity="INFO",
                        task_type="PROJECT",
                        title=f"[Project Hub] {card['title']}",
                        details=(card["description"] or "")[:1200],
                        created_by=actor,
                    )
                )

            if linked_task_id is None:
                raise ValueError("task_id_or_creator_required")

            con.execute(
                "UPDATE project_cards SET linked_task_id = ?, updated_at = ? WHERE id = ?",
                (linked_task_id, self._now(), card_id),
            )
            self._log_activity(
                con,
                tenant_id=tenant_id,
                actor=actor,
                action="CARD_TASK_LINKED",
                resource=f"card:{card_id}",
                details=f"Karte '{card['title']}' mit Task {linked_task_id} verknuepft.",
                board_id=card["board_id"],
                card_id=card_id,
                payload={"linked_task_id": linked_task_id},
                importance=7,
            )
            con.commit()
            updated = con.execute("SELECT * FROM project_cards WHERE id = ?", (card_id,)).fetchone()
            return dict(updated)
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def start_timer_for_card(
        self,
        *,
        tenant_id: str,
        card_id: str,
        actor: str,
        timer_start_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not callable(timer_start_fn):
            raise RuntimeError("timer_unavailable")

        con = self.db._db()
        try:
            card = con.execute(
                "SELECT * FROM project_cards WHERE id = ? AND tenant_id = ? AND archived = 0",
                (card_id, tenant_id),
            ).fetchone()
            if not card:
                raise PermissionError("card_not_found_or_forbidden")
        finally:
            con.close()

        timer_entry = timer_start_fn(
            tenant_id=tenant_id,
            user=actor,
            project_id=None,
            note=f"Project Hub Card {card_id}: {card['title']}",
        )

        con2 = self.db._db()
        try:
            self._log_activity(
                con2,
                tenant_id=tenant_id,
                actor=actor,
                action="CARD_TIMER_STARTED",
                resource=f"card:{card_id}",
                details=f"Timer fuer Karte '{card['title']}' gestartet.",
                board_id=card["board_id"],
                card_id=card_id,
                payload={"timer_entry": timer_entry},
                importance=6,
            )
            con2.commit()
        except Exception:
            con2.rollback()
            raise
        finally:
            con2.close()

        return timer_entry

    # ---------------------------------------------------------------------
    # Legacy task-table compatibility for existing web flows.
    # ---------------------------------------------------------------------
    def create_task(self, board_id: str, title: str, column: str = "To Do", **kwargs: Any) -> str:
        actor, role, tenant_id = self._context_identity()
        status = COLUMN_TO_STATUS.get(column, "OPEN")
        task_id = self.create_team_task(
            tenant_id=tenant_id,
            actor=actor,
            actor_role=role,
            title=title,
            description=str(kwargs.get("content") or ""),
            priority=str(kwargs.get("priority") or "MEDIUM"),
            due_at=str(kwargs.get("due") or ""),
            assigned_to=str(kwargs.get("assigned") or actor),
            board_id=board_id,
            source_type=str(kwargs.get("source_type") or ""),
            source_ref=str(kwargs.get("source_ref") or ""),
        )
        if status != "OPEN":
            self.update_task_column(task_id, STATUS_TO_COLUMN[status])
        return task_id

    def _fetch_task(self, con, task_id: str) -> dict[str, Any] | None:
        row = con.execute("SELECT * FROM team_tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def _transition_status(
        self,
        con,
        *,
        task: dict[str, Any],
        actor: str,
        actor_role: str,
        new_status: str,
        reason: str = "",
    ) -> None:
        current = str(task.get("status") or "OPEN")
        task_id = str(task["id"])
        tenant_id = str(task["tenant_id"])
        assignee = str(task.get("assigned_to") or "")
        title = str(task.get("title") or "")
        allowed_for_actor = (
            actor == assignee
            or actor == str(task.get("created_by") or "")
            or self._role_allows(actor_role, "MANAGER")
        )
        if not allowed_for_actor:
            raise PermissionError("task_action_forbidden")
        if new_status == "REJECTED" and not reason.strip():
            raise ValueError("reject_reason_required")
        if new_status == "DONE" and current not in {"IN_PROGRESS", "OPEN"}:
            raise ValueError("invalid_transition_done")
        if new_status == "IN_PROGRESS" and current not in {"OPEN", "IN_PROGRESS"}:
            raise ValueError("invalid_transition_in_progress")
        if new_status == "REJECTED" and current == "DONE":
            raise ValueError("invalid_transition_rejected")

        con.execute(
            "UPDATE team_tasks SET status=?, rejection_reason=?, updated_at=? WHERE id=?",
            (
                new_status,
                reason.strip() if new_status == "REJECTED" else None,
                self._now_iso(),
                task_id,
            ),
        )
        self._log_task_event(
            con,
            task_id=task_id,
            tenant_id=tenant_id,
            actor=actor,
            action=f"STATUS_{new_status}",
            reason=reason,
        )
        self._audit_activity(
            con,
            tenant_id=tenant_id,
            username=actor,
            action="TASK_STATUS_CHANGED",
            resource=f"team_task:{task_id}",
            details=f"{current}->{new_status}",
        )
        self._notify(
            con,
            tenant_id=tenant_id,
            username=str(task.get("created_by") or ""),
            task_id=task_id,
            kind="TASK_STATUS",
            message=f"Aufgabe '{title[:80]}' ist jetzt {new_status}.",
        )

    def execute_task_command(self, command: dict[str, Any]) -> dict[str, Any]:
        action = str(command.get("action") or "").strip().lower()
        if not action:
            raise ValueError("action_required")

        actor, actor_role, tenant_id = self._context_identity()
        con = self.db._db()
        try:
            if action == "create":
                task_id = self.create_team_task(
                    tenant_id=tenant_id,
                    actor=actor,
                    actor_role=actor_role,
                    title=str(command.get("title") or ""),
                    description=str(command.get("description") or ""),
                    priority=str(command.get("priority") or "MEDIUM"),
                    due_at=str(command.get("due_at") or ""),
                    assigned_to=str(command.get("assigned_to") or actor),
                    board_id=str(command.get("board_id") or "") or None,
                    source_type=str(command.get("source_type") or ""),
                    source_ref=str(command.get("source_ref") or ""),
                )
                return {"ok": True, "task_id": task_id}

            task_id = str(command.get("task_id") or "").strip()
            if not task_id:
                raise ValueError("task_id_required")
            task = self._fetch_task(con, task_id)
            if not task:
                raise ValueError("task_not_found")
            if str(task.get("tenant_id") or "") != tenant_id and not self._role_allows(
                actor_role, "ADMIN"
            ):
                raise PermissionError("cross_tenant_forbidden")

            if action in {"accept", "start"}:
                self._transition_status(
                    con,
                    task=task,
                    actor=actor,
                    actor_role=actor_role,
                    new_status="IN_PROGRESS",
                )
            elif action in {"complete", "done"}:
                self._transition_status(
                    con,
                    task=task,
                    actor=actor,
                    actor_role=actor_role,
                    new_status="DONE",
                )
            elif action == "reject":
                self._transition_status(
                    con,
                    task=task,
                    actor=actor,
                    actor_role=actor_role,
                    new_status="REJECTED",
                    reason=str(command.get("reason") or ""),
                )
            elif action == "delegate":
                to_user = str(command.get("to_user") or "").strip()
                reason = str(command.get("reason") or "").strip()
                if not to_user:
                    raise ValueError("delegate_user_required")
                if not self._user_exists(con, tenant_id, to_user):
                    raise ValueError("delegate_target_not_registered")
                assignee = str(task.get("assigned_to") or "")
                if actor != assignee and not self._role_allows(actor_role, "MANAGER"):
                    raise PermissionError("delegate_forbidden")
                con.execute(
                    "UPDATE team_tasks SET assigned_to=?, status='OPEN', updated_at=? WHERE id=?",
                    (to_user, self._now_iso(), task_id),
                )
                self._log_task_event(
                    con,
                    task_id=task_id,
                    tenant_id=tenant_id,
                    actor=actor,
                    action="TASK_DELEGATED",
                    reason=reason,
                    from_user=assignee,
                    to_user=to_user,
                )
                self._audit_activity(
                    con,
                    tenant_id=tenant_id,
                    username=actor,
                    action="TASK_DELEGATED",
                    resource=f"team_task:{task_id}",
                    details=f"{assignee}->{to_user}",
                )
                self._notify(
                    con,
                    tenant_id=tenant_id,
                    username=to_user,
                    task_id=task_id,
                    kind="TASK_DELEGATED",
                    message=f"Dir wurde Aufgabe '{str(task.get('title') or '')[:100]}' delegiert.",
                )
            elif action == "mark_notification_read":
                notification_id = int(command.get("notification_id") or 0)
                if notification_id <= 0:
                    raise ValueError("notification_id_required")
                con.execute(
                    """
                    UPDATE team_task_notifications SET is_read=1
                    WHERE id=? AND tenant_id=? AND username=?
                    """,
                    (notification_id, tenant_id, actor),
                )
            else:
                raise ValueError(f"unsupported_action:{action}")

            con.commit()
            return {"ok": True, "task_id": task_id}
        finally:
            con.close()

    def update_task_column(self, task_id: str, new_column: str) -> None:
        con = self.db._db()
        try:
            parsed: dict[str, Any] | None = None
            try:
                parsed_candidate = json.loads(str(new_column or "").strip())
                if isinstance(parsed_candidate, dict) and parsed_candidate.get("action"):
                    parsed = parsed_candidate
            except Exception:
                parsed = None

            if parsed is not None:
                if str(parsed.get("task_id") or "") == "" and task_id not in {"__cmd__", ""}:
                    parsed["task_id"] = task_id
                try:
                    result = self.execute_task_command(parsed)
                    con.commit()
                    return result
                except (ValueError, PermissionError) as exc:
                    return {"ok": False, "error": str(exc)}

            row = con.execute("SELECT id FROM team_tasks WHERE id=?", (task_id,)).fetchone()
            if row:
                mapped_status = COLUMN_TO_STATUS.get(str(new_column), "OPEN")
                actor, role, _tenant_id = self._context_identity()
                full_task = self._fetch_task(con, task_id)
                if not full_task:
                    raise ValueError("task_not_found")
                try:
                    self._transition_status(
                        con,
                        task=full_task,
                        actor=actor,
                        actor_role=role,
                        new_status=mapped_status,
                    )
                    con.commit()
                    return {"ok": True, "task_id": task_id}
                except (ValueError, PermissionError) as exc:
                    return {"ok": False, "error": str(exc)}

            # Legacy board fallback.
            con.execute("UPDATE tasks SET column_name = ? WHERE id = ?", (new_column, task_id))
            con.commit()
            return {"ok": True, "task_id": task_id, "legacy": True}
        finally:
            con.close()

    def _load_task_attachments(self, con, tenant_id: str) -> dict[str, list[dict[str, Any]]]:
        rows = con.execute(
            """
            SELECT task_id, kind, value, scan_status, metadata_json
            FROM team_task_attachments
            WHERE tenant_id=?
            ORDER BY created_at DESC
            """,
            (tenant_id,),
        ).fetchall()
        out: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            key = str(row["task_id"])
            out.setdefault(key, []).append(
                {
                    "kind": str(row["kind"] or ""),
                    "value": str(row["value"] or ""),
                    "scan_status": str(row["scan_status"] or ""),
                    "metadata": json.loads(str(row["metadata_json"] or "{}")),
                }
            )
        return out

    def list_tasks(self, board_id: str) -> dict[str, Any]:
        actor, role, tenant_id = self._context_identity()
        con = self.db._db()
        try:
            team_rows = con.execute(
                """
                SELECT *
                FROM team_tasks
                WHERE tenant_id=?
                ORDER BY
                  CASE priority
                    WHEN 'CRITICAL' THEN 0
                    WHEN 'HIGH' THEN 1
                    WHEN 'MEDIUM' THEN 2
                    ELSE 3
                  END ASC,
                  COALESCE(due_at, '9999-12-31T23:59:59') ASC,
                  created_at DESC
                """,
                (tenant_id,),
            ).fetchall()
            attachments_map = self._load_task_attachments(con, tenant_id)
            notifications = [
                dict(row)
                for row in con.execute(
                    """
                    SELECT id, task_id, kind, message, is_read, created_at
                    FROM team_task_notifications
                    WHERE tenant_id=? AND username=?
                    ORDER BY id DESC
                    LIMIT 100
                    """,
                    (tenant_id, actor),
                ).fetchall()
            ]
            users = [
                str(row["username"] or "")
                for row in con.execute(
                    "SELECT username FROM memberships WHERE tenant_id=? ORDER BY username",
                    (tenant_id,),
                ).fetchall()
            ]

            tasks: list[dict[str, Any]] = []
            for row in team_rows:
                task = dict(row)
                task_id = str(task["id"])
                assignee = str(task.get("assigned_to") or "")
                task["column_name"] = STATUS_TO_COLUMN.get(str(task.get("status") or "OPEN"), "To Do")
                task["content"] = str(task.get("description") or "")
                task["assigned_user"] = assignee
                task["is_incoming"] = assignee == actor and str(task.get("status") or "") == "OPEN"
                task["attachments"] = attachments_map.get(task_id, [])
                task["can_accept"] = assignee == actor and str(task.get("status") or "") == "OPEN"
                task["can_reject"] = assignee == actor and str(task.get("status") or "") in {"OPEN", "IN_PROGRESS"}
                task["can_delegate"] = assignee == actor or self._role_allows(role, "MANAGER")
                task["can_complete"] = assignee == actor and str(task.get("status") or "") in {"OPEN", "IN_PROGRESS"}
                tasks.append(task)

            if not tasks:
                legacy_rows = con.execute(
                    "SELECT * FROM tasks WHERE board_id = ? ORDER BY created_at DESC",
                    (board_id,),
                ).fetchall()
                tasks = [dict(r) for r in legacy_rows]

            return {
                "items": tasks,
                "inbox": [t for t in tasks if bool(t.get("is_incoming"))],
                "notifications": notifications,
                "badge_count": len([n for n in notifications if int(n.get("is_read") or 0) == 0]),
                "users": users,
                "viewer": {"user": actor, "role": role, "tenant_id": tenant_id},
            }
        finally:
            con.close()

    def get_gantt_data(self, project_id: str) -> List[Dict[str, Any]]:
        con = self.db._db()
        try:
            rows = con.execute(
                """SELECT t.id, t.title, t.due_date, t.created_at, b.name as board_name
                   FROM tasks t JOIN boards b ON t.board_id = b.id
                   WHERE b.project_id = ?""",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def add_relation(self, task_id: str, related_id: str, rel_type: str = "relates") -> None:
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO task_relations(task_id, related_task_id, relation_type) VALUES (?,?,?)",
                (task_id, related_id, rel_type),
            )
            con.commit()
        finally:
            con.close()

    def add_checklist_item(self, task_id: str, content: str) -> str:
        cl_id = str(uuid.uuid4())
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO task_checklists(id, task_id, content) VALUES (?,?,?)",
                (cl_id, task_id, content),
            )
            con.commit()
            return cl_id
        finally:
            con.close()
