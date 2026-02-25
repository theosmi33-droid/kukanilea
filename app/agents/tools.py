from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type

from pydantic import BaseModel, Field, ValidationError

from app.config import Config

from . import retrieval_fts


class CreateTaskArgs(BaseModel):
    title: str
    severity: str = "INFO"
    task_type: str = "GENERAL"
    details: str = ""


class LogTimeArgs(BaseModel):
    minutes: int = Field(ge=1, le=1440)
    note: str = ""
    project_id: Optional[int] = None


class ExportAkteArgs(BaseModel):
    task_id: int = Field(gt=0)


@dataclass
class ToolSpec:
    name: str
    args_model: Type[BaseModel]
    is_mutating: bool
    handler: Callable[..., Dict[str, Any]]


def _core_web_module():
    from app import web

    return web


def _create_task_handler(
    *, tenant_id: str, user: str, args: CreateTaskArgs
) -> Dict[str, Any]:
    web = _core_web_module()
    core_mod = getattr(web, "core", None)
    creator = getattr(core_mod, "task_create", None)
    if not callable(creator):
        raise RuntimeError("task_create_unavailable")
    task_id = int(
        creator(
            tenant=tenant_id,
            severity=args.severity,
            task_type=args.task_type,
            title=args.title,
            details=args.details,
            created_by=user,
        )
    )
    retrieval_fts.enqueue("task", task_id, "upsert")
    return {"task_id": task_id}


def _log_time_handler(
    *, tenant_id: str, user: str, args: LogTimeArgs
) -> Dict[str, Any]:
    web = _core_web_module()
    core_mod = getattr(web, "core", None)
    starter = getattr(core_mod, "time_entry_start", None)
    stopper = getattr(core_mod, "time_entry_stop", None)
    if not callable(starter) or not callable(stopper):
        raise RuntimeError("time_tracking_unavailable")

    started_at = (
        datetime.now(timezone.utc) - timedelta(minutes=args.minutes)
    ).isoformat(timespec="seconds")
    entry = starter(
        tenant_id=tenant_id,
        user=user,
        project_id=args.project_id,
        note=args.note,
        started_at=started_at,
    )
    entry_id = int((entry or {}).get("id") or 0)
    if entry_id <= 0:
        raise RuntimeError("time_entry_create_failed")
    stopped = stopper(tenant_id=tenant_id, user=user, entry_id=entry_id)
    retrieval_fts.enqueue("time_entry", entry_id, "upsert")
    return {"entry_id": entry_id, "duration_minutes": args.minutes, "entry": stopped}


def _export_akte_handler(
    *, tenant_id: str, user: str, args: ExportAkteArgs
) -> Dict[str, Any]:
    core_db = Path(Config.CORE_DB)
    if not core_db.exists():
        raise RuntimeError("core_db_missing")

    import sqlite3

    con = sqlite3.connect(str(core_db))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT * FROM tasks WHERE id=?", (args.task_id,)).fetchone()
    finally:
        con.close()

    if not row:
        raise RuntimeError("task_not_found")

    export_dir = Path(Config.USER_DATA_ROOT) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    out = export_dir / f"akte_task_{args.task_id}.json"
    payload = {
        "tenant_id": tenant_id,
        "exported_by": user,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "task": dict(row),
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"file": str(out)}


TOOL_REGISTRY: Dict[str, ToolSpec] = {
    "create_task": ToolSpec(
        name="create_task",
        args_model=CreateTaskArgs,
        is_mutating=True,
        handler=_create_task_handler,
    ),
    "log_time": ToolSpec(
        name="log_time",
        args_model=LogTimeArgs,
        is_mutating=True,
        handler=_log_time_handler,
    ),
    "export_akte": ToolSpec(
        name="export_akte",
        args_model=ExportAkteArgs,
        is_mutating=True,
        handler=_export_akte_handler,
    ),
}


def dispatch(
    name: str,
    args_dict: Dict[str, Any],
    *,
    read_only_flag: bool,
    tenant_id: str,
    user: str,
) -> Dict[str, Any]:
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return {
            "result": {},
            "error": {"code": "unknown_tool", "msg": f"Unbekanntes Tool: {name}"},
        }

    if tool.is_mutating and read_only_flag:
        return {
            "result": {},
            "error": {
                "code": "read_only",
                "msg": "Instanz ist schreibgeschuetzt; mutierende Tools sind deaktiviert.",
            },
        }

    try:
        parsed = tool.args_model.model_validate(args_dict or {})
    except ValidationError as exc:
        return {
            "result": {},
            "error": {"code": "validation_error", "msg": exc.errors()[0]["msg"]},
        }

    try:
        result = tool.handler(tenant_id=tenant_id, user=user, args=parsed)
        return {"result": result, "error": None}
    except Exception as exc:
        return {
            "result": {},
            "error": {"code": "tool_failed", "msg": f"{tool.name}: {exc}"},
        }
