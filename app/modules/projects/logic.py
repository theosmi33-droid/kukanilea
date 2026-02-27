"""
app/modules/projects/logic.py
Kanban & Project management engine for KUKANILEA v2.1.
Handles Step 71-85 (projects, boards, tasks).
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

class ProjectManager:
    def __init__(self, db_ext):
        self.db = db_ext

    def create_project(self, tenant_id: str, name: str, description: str = "") -> str:
        """Step 71: Create projects table."""
        p_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO projects(id, tenant_id, name, description, created_at) VALUES (?,?,?,?,?)",
                (p_id, tenant_id, name, description, now)
            )
            con.commit()
            return p_id
        finally:
            con.close()

    def create_board(self, project_id: str, name: str) -> str:
        """Step 72: Create boards."""
        b_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO boards(id, project_id, name, created_at) VALUES (?,?,?,?)",
                (b_id, project_id, name, now)
            )
            con.commit()
            return b_id
        finally:
            con.close()

    def create_task(self, board_id: str, title: str, column: str = "To Do", **kwargs) -> str:
        """Step 74: Create tasks + Step 126: Activity Log."""
        t_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        con = self.db._db()
        try:
            con.execute(
                """INSERT INTO tasks(id, board_id, column_name, title, content, assigned_user, due_date, priority, created_at) 
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (t_id, board_id, column, title, kwargs.get("content"), kwargs.get("assigned"), 
                 kwargs.get("due"), kwargs.get("priority"), now)
            )
            # Step 126: Activity Log (simplified via Audit Table)
            self._log_activity(con, board_id, "TASK_CREATED", t_id, f"Task '{title}' created.")
            con.commit()
            return t_id
        finally:
            con.close()

    def add_relation(self, task_id: str, related_id: str, rel_type: str = "relates"):
        """Step 117: Task relationships ('blocks', 'duplicate')."""
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO task_relations(task_id, related_task_id, relation_type) VALUES (?,?,?)",
                (task_id, related_id, rel_type)
            )
            con.commit()
        finally:
            con.close()

    def add_checklist_item(self, task_id: str, content: str) -> str:
        """Step 120: Checklist items."""
        cl_id = str(uuid.uuid4())
        con = self.db._db()
        try:
            con.execute(
                "INSERT INTO task_checklists(id, task_id, content) VALUES (?,?,?)",
                (cl_id, task_id, content)
            )
            con.commit()
            return cl_id
        finally:
            con.close()

    def get_gantt_data(self, project_id: str):
        """Step 129: Data for Gantt-View."""
        con = self.db._db()
        try:
            rows = con.execute(
                """SELECT t.id, t.title, t.due_date, t.created_at, b.name as board_name 
                   FROM tasks t JOIN boards b ON t.board_id = b.id 
                   WHERE b.project_id = ?""", (project_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def _log_activity(self, con, board_id: str, action: str, resource: str, details: str):
        """Internal helper for Activity Feed (Step 126)."""
        now = datetime.now().isoformat()
        # Note: In real app, get current user/tenant from context
        con.execute(
            "INSERT INTO audit_log(ts, tenant_id, username, action, resource, details) VALUES (?,?,?,?,?,?)",
            (now, "SYSTEM", "system", action, resource, details)
        )

    def update_task_column(self, task_id: str, new_column: str):
        """Step 75: Drag and drop tasks (Backend part)."""
        con = self.db._db()
        try:
            con.execute("UPDATE tasks SET column_name = ? WHERE id = ?", (new_column, task_id))
            con.commit()
        finally:
            con.close()
            
    def list_tasks(self, board_id: str) -> List[Dict[str, Any]]:
        """Step 84: Task list/search."""
        con = self.db._db()
        try:
            rows = con.execute("SELECT * FROM tasks WHERE board_id = ?", (board_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()
