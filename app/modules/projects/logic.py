"""
app/modules/projects/logic.py
Kanban and task management engine for local-first team workflows.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import has_request_context, session

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
    def __init__(self, db_ext):
        self.db = db_ext
        self._ensure_team_task_schema()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

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

    def create_project(self, tenant_id: str, name: str, description: str = "") -> str:
        p_id = str(uuid.uuid4())
        now = self._now_iso()
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO projects(id, tenant_id, name, description, created_at) VALUES (?,?,?,?,?)",
                (p_id, tenant_id, name, description, now),
            )
            con.commit()
            return p_id
        finally:
            con.close()

    def create_board(self, project_id: str, name: str) -> str:
        b_id = str(uuid.uuid4())
        now = self._now_iso()
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO boards(id, project_id, name, created_at) VALUES (?,?,?,?)",
                (b_id, project_id, name, now),
            )
            con.commit()
            return b_id
        finally:
            con.close()

    def create_task(self, board_id: str, title: str, column: str = "To Do", **kwargs) -> str:
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
            attachment_link=str(kwargs.get("attachment_link") or ""),
            attachment_upload_path=str(kwargs.get("attachment_upload_path") or ""),
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
                    attachment_link=str(command.get("attachment_link") or ""),
                    attachment_upload_path=str(command.get("attachment_upload_path") or ""),
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

    def add_relation(self, task_id: str, related_id: str, rel_type: str = "relates"):
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

    def get_gantt_data(self, project_id: str):
        con = self.db._db()
        try:
            rows = con.execute(
                """
                SELECT t.id, t.title, t.due_date, t.created_at, b.name as board_name
                FROM tasks t JOIN boards b ON t.board_id = b.id
                WHERE b.project_id = ?
                """,
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def update_task_column(self, task_id: str, new_column: str):
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
