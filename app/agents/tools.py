from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.ai.knowledge import store_entity
from app.config import Config
from app.knowledge import knowledge_search
from app.lead_intake import leads_create
from app.mail import (
    postfach_create_draft,
    postfach_create_followup_task,
    postfach_extract_intake,
    postfach_extract_structured,
    postfach_get_thread,
    postfach_link_entities,
    postfach_list_threads,
    postfach_send_draft,
    postfach_sync_account,
)

from . import retrieval_fts


class CreateTaskArgs(BaseModel):
    title: str
    severity: str = "INFO"
    task_type: str = "GENERAL"
    details: str = ""


class SearchContactsArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


class SearchDocumentsArgs(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


class LogTimeArgs(BaseModel):
    minutes: int = Field(ge=1, le=1440)
    note: str = ""
    project_id: int | None = None


class ExportAkteArgs(BaseModel):
    task_id: int = Field(gt=0)


class PostfachSyncArgs(BaseModel):
    account_id: str = Field(min_length=1)
    limit: int = Field(default=50, ge=1, le=200)
    since: str | None = None


class PostfachListThreadsArgs(BaseModel):
    account_id: str = Field(min_length=1)
    filter: str = ""
    limit: int = Field(default=50, ge=1, le=500)


class PostfachGetThreadArgs(BaseModel):
    thread_id: str = Field(min_length=1)


class PostfachDraftReplyArgs(BaseModel):
    thread_id: str = Field(min_length=1)
    intent: str = ""
    tone: str = "neutral"
    template_id: str | None = None
    citations_required: bool = True


class PostfachSendDraftArgs(BaseModel):
    draft_id: str = Field(min_length=1)
    user_confirmed: bool = False


class PostfachLinkEntitiesArgs(BaseModel):
    thread_id: str = Field(min_length=1)
    customer_id: str | None = None
    project_id: str | None = None
    lead_id: str | None = None


class PostfachExtractStructuredArgs(BaseModel):
    thread_id: str = Field(min_length=1)
    schema_name: str = "default"


class PostfachCreateFollowupArgs(BaseModel):
    thread_id: str = Field(min_length=1)
    due_at: str
    owner: str
    title: str = "Postfach Follow-up"


class PostfachExtractIntakeArgs(BaseModel):
    thread_id: str = Field(min_length=1)


class PostfachCreateLeadFromThreadArgs(BaseModel):
    thread_id: str = Field(min_length=1)


class PostfachCreateCaseFromThreadArgs(BaseModel):
    thread_id: str = Field(min_length=1)


class PostfachCreateTasksFromThreadArgs(BaseModel):
    thread_id: str = Field(min_length=1)


@dataclass
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    is_mutating: bool
    handler: Callable[..., dict[str, Any]]


def _core_web_module():
    from app import web

    return web


def _create_task_via_web(
    *,
    tenant_id: str,
    user: str,
    title: str,
    details: str,
    severity: str = "INFO",
    task_type: str = "GENERAL",
) -> int:
    web = _core_web_module()
    creator = getattr(web, "task_create", None)
    if not callable(creator):
        raise RuntimeError("task_create_unavailable")
    task_id = int(
        creator(
            tenant=tenant_id,
            severity=severity,
            task_type=task_type,
            title=title,
            details=details,
            created_by=user,
        )
    )
    retrieval_fts.enqueue("task", task_id, "upsert")
    return task_id


def _create_task_handler(
    *, tenant_id: str, user: str, args: CreateTaskArgs
) -> dict[str, Any]:
    task_id = _create_task_via_web(
        tenant_id=tenant_id,
        user=user,
        title=args.title,
        details=args.details,
        severity=args.severity,
        task_type=args.task_type,
    )
    try:
        store_entity(
            "task",
            task_id,
            f"{args.title} {args.details}",
            {
                "tenant_id": tenant_id,
                "severity": args.severity,
                "task_type": args.task_type,
            },
        )
    except Exception:
        pass
    return {"task_id": task_id}


def _search_contacts_handler(
    *, tenant_id: str, user: str, args: SearchContactsArgs
) -> dict[str, Any]:
    _ = user
    db_path = Path(Config.CORE_DB)
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT c.id,
                   c.name,
                   c.email,
                   c.phone,
                   c.role,
                   c.customer_id,
                   cu.name AS customer_name
            FROM contacts c
            LEFT JOIN customers cu
              ON cu.id=c.customer_id
             AND cu.tenant_id=c.tenant_id
            WHERE c.tenant_id=?
              AND (
                LOWER(COALESCE(c.name,'')) LIKE LOWER(?)
                OR LOWER(COALESCE(c.email,'')) LIKE LOWER(?)
                OR LOWER(COALESCE(c.phone,'')) LIKE LOWER(?)
                OR LOWER(COALESCE(c.role,'')) LIKE LOWER(?)
                OR LOWER(COALESCE(cu.name,'')) LIKE LOWER(?)
              )
            ORDER BY c.updated_at DESC, c.id DESC
            LIMIT ?
            """,
            (
                tenant_id,
                f"%{args.query}%",
                f"%{args.query}%",
                f"%{args.query}%",
                f"%{args.query}%",
                f"%{args.query}%",
                int(args.limit),
            ),
        ).fetchall()
    finally:
        con.close()

    contacts = []
    for row in rows:
        contacts.append(
            {
                "id": str(row["id"] or ""),
                "name": str(row["name"] or ""),
                "email": str(row["email"] or ""),
                "phone": str(row["phone"] or ""),
                "role": str(row["role"] or ""),
                "customer_id": str(row["customer_id"] or ""),
                "customer_name": str(row["customer_name"] or ""),
            }
        )
    return {"count": len(contacts), "contacts": contacts}


def _search_documents_handler(
    *, tenant_id: str, user: str, args: SearchDocumentsArgs
) -> dict[str, Any]:
    _ = user
    rows = knowledge_search(tenant_id=tenant_id, query=args.query, limit=args.limit)
    items = []
    for row in rows:
        items.append(
            {
                "chunk_id": str(row.get("chunk_id") or ""),
                "source_type": str(row.get("source_type") or ""),
                "source_ref": str(row.get("source_ref") or ""),
                "title": str(row.get("title") or ""),
                "snippet": str(row.get("snippet") or ""),
                "score": float(row.get("score") or 0.0),
                "updated_at": str(row.get("updated_at") or ""),
            }
        )
    return {"count": len(items), "documents": items}


def _log_time_handler(
    *, tenant_id: str, user: str, args: LogTimeArgs
) -> dict[str, Any]:
    web = _core_web_module()
    starter = getattr(web, "time_entry_start", None)
    stopper = getattr(web, "time_entry_stop", None)
    if not callable(starter) or not callable(stopper):
        raise RuntimeError("time_tracking_unavailable")

    started_at = (
        datetime.now(UTC) - timedelta(minutes=args.minutes)
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
) -> dict[str, Any]:
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
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "task": dict(row),
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"file": str(out)}


def _postfach_sync_handler(
    *, tenant_id: str, user: str, args: PostfachSyncArgs
) -> dict[str, Any]:
    _ = user
    result = postfach_sync_account(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        account_id=args.account_id,
        limit=args.limit,
        since=args.since,
    )
    if not result.get("ok"):
        raise RuntimeError(str(result.get("reason") or "postfach_sync_failed"))
    return result


def _postfach_list_threads_handler(
    *, tenant_id: str, user: str, args: PostfachListThreadsArgs
) -> dict[str, Any]:
    _ = user
    rows = postfach_list_threads(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        account_id=args.account_id,
        filter_text=args.filter,
        limit=args.limit,
    )
    return {"count": len(rows), "threads": rows}


def _postfach_get_thread_handler(
    *, tenant_id: str, user: str, args: PostfachGetThreadArgs
) -> dict[str, Any]:
    _ = user
    data = postfach_get_thread(
        Path(Config.CORE_DB), tenant_id=tenant_id, thread_id=args.thread_id
    )
    if not data:
        raise RuntimeError("thread_not_found")
    return data


def _postfach_draft_reply_handler(
    *, tenant_id: str, user: str, args: PostfachDraftReplyArgs
) -> dict[str, Any]:
    thread_data = postfach_get_thread(
        Path(Config.CORE_DB), tenant_id=tenant_id, thread_id=args.thread_id
    )
    if not thread_data:
        raise RuntimeError("thread_not_found")
    thread = thread_data["thread"]
    messages = thread_data.get("messages", [])
    last_msg = messages[-1] if messages else {}
    subject = str(
        last_msg.get("subject_redacted") or thread.get("subject_redacted") or ""
    ).strip()
    tone = (args.tone or "neutral").strip()
    intent = (args.intent or "antworten").strip()
    citations = "Ja" if bool(args.citations_required) else "Nein"
    body = (
        "Guten Tag,\n\n"
        f"vielen Dank fuer Ihre Nachricht ({intent}). "
        f"Wir haben Ihr Anliegen mit Tonalitaet '{tone}' aufgenommen.\n\n"
        "Naechste Schritte:\n"
        "- Eingang geprueft\n"
        "- Rueckmeldung vorbereitet\n"
        f"- Quellenhinweise erforderlich: {citations}\n\n"
        f"Thread-ID: {args.thread_id}\n"
        f"Bearbeiter: {user}\n\n"
        "Mit freundlichen Gruessen\n"
        "KUKANILEA Systems"
    )
    draft_id = postfach_create_draft(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        account_id=str(thread.get("account_id") or ""),
        thread_id=str(thread.get("id") or args.thread_id),
        to_value=str(last_msg.get("from_redacted") or ""),
        subject_value=f"Re: {subject}" if subject else "Re: Ihre Anfrage",
        body_value=body,
    )
    return {"draft_id": draft_id, "thread_id": args.thread_id}


def _postfach_send_draft_handler(
    *, tenant_id: str, user: str, args: PostfachSendDraftArgs
) -> dict[str, Any]:
    _ = user
    result = postfach_send_draft(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        draft_id=args.draft_id,
        user_confirmed=bool(args.user_confirmed),
    )
    if not result.get("ok"):
        raise RuntimeError(str(result.get("reason") or "postfach_send_failed"))
    return result


def _postfach_link_entities_handler(
    *, tenant_id: str, user: str, args: PostfachLinkEntitiesArgs
) -> dict[str, Any]:
    _ = user
    return postfach_link_entities(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        thread_id=args.thread_id,
        customer_id=args.customer_id,
        project_id=args.project_id,
        lead_id=args.lead_id,
    )


def _postfach_extract_structured_handler(
    *, tenant_id: str, user: str, args: PostfachExtractStructuredArgs
) -> dict[str, Any]:
    _ = user
    return postfach_extract_structured(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        thread_id=args.thread_id,
        schema_name=args.schema_name,
    )


def _postfach_extract_intake_handler(
    *, tenant_id: str, user: str, args: PostfachExtractIntakeArgs
) -> dict[str, Any]:
    _ = user
    return postfach_extract_intake(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        thread_id=args.thread_id,
        schema_name="intake_v1",
    )


def _postfach_create_followup_handler(
    *, tenant_id: str, user: str, args: PostfachCreateFollowupArgs
) -> dict[str, Any]:
    return postfach_create_followup_task(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        thread_id=args.thread_id,
        due_at=args.due_at,
        owner=args.owner,
        title=args.title,
        created_by=user,
    )


def _postfach_create_lead_from_thread_handler(
    *, tenant_id: str, user: str, args: PostfachCreateLeadFromThreadArgs
) -> dict[str, Any]:
    data = postfach_get_thread(
        Path(Config.CORE_DB), tenant_id=tenant_id, thread_id=args.thread_id
    )
    if not data:
        raise RuntimeError("thread_not_found")
    thread = data.get("thread") or {}
    messages = data.get("messages") or []
    newest = messages[-1] if messages else {}
    subject = str(
        thread.get("subject_redacted")
        or newest.get("subject_redacted")
        or "Neue Anfrage"
    )
    message = str(newest.get("redacted_text") or "Anfrage aus Postfach")
    lead_id = leads_create(
        tenant_id=tenant_id,
        source="email",
        contact_name="Postfach Anfrage",
        contact_email="postfach.request@kukanilea.local",
        contact_phone="+490000000000",
        subject=subject[:500],
        message=message[:20000],
        actor_user_id=user,
    )
    postfach_link_entities(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        thread_id=args.thread_id,
        lead_id=lead_id,
    )
    return {"lead_id": lead_id, "thread_id": args.thread_id}


def _postfach_create_case_from_thread_handler(
    *, tenant_id: str, user: str, args: PostfachCreateCaseFromThreadArgs
) -> dict[str, Any]:
    data = postfach_get_thread(
        Path(Config.CORE_DB), tenant_id=tenant_id, thread_id=args.thread_id
    )
    if not data:
        raise RuntimeError("thread_not_found")
    thread = data.get("thread") or {}
    title = f"Case: {str(thread.get('subject_redacted') or args.thread_id)[:160]}"
    details = f"Postfach Thread: {args.thread_id}"
    case_task_id = _create_task_via_web(
        tenant_id=tenant_id,
        user=user,
        title=title,
        details=details,
        severity="INFO",
        task_type="CASE",
    )
    return {"case_id": case_task_id, "thread_id": args.thread_id}


def _postfach_create_tasks_from_thread_handler(
    *, tenant_id: str, user: str, args: PostfachCreateTasksFromThreadArgs
) -> dict[str, Any]:
    intake = postfach_extract_intake(
        Path(Config.CORE_DB),
        tenant_id=tenant_id,
        thread_id=args.thread_id,
        schema_name="intake_v1",
    )
    if not intake.get("ok"):
        raise RuntimeError(str(intake.get("reason") or "intake_failed"))
    fields = intake.get("fields") or {}
    intent = str(fields.get("intent") or "general_inquiry")
    base_title = f"Postfach {intent}: {args.thread_id[:8]}"
    task_ids = [
        _create_task_via_web(
            tenant_id=tenant_id,
            user=user,
            title=base_title,
            details=f"Automatisch aus Thread {args.thread_id}",
            severity="INFO",
            task_type="FOLLOWUP",
        )
    ]
    if str(intent) in {"complaint", "quote_request"}:
        task_ids.append(
            _create_task_via_web(
                tenant_id=tenant_id,
                user=user,
                title=f"Klaerung: {base_title}",
                details=f"Zusatz-Task fuer Intent {intent}",
                severity="INFO",
                task_type="GENERAL",
            )
        )
    return {"task_ids": task_ids, "thread_id": args.thread_id, "intent": intent}


def _postfach_specs() -> dict[str, ToolSpec]:
    specs = {
        "postfach_sync": ToolSpec(
            name="postfach_sync",
            args_model=PostfachSyncArgs,
            is_mutating=True,
            handler=_postfach_sync_handler,
        ),
        "postfach_list_threads": ToolSpec(
            name="postfach_list_threads",
            args_model=PostfachListThreadsArgs,
            is_mutating=False,
            handler=_postfach_list_threads_handler,
        ),
        "postfach_get_thread": ToolSpec(
            name="postfach_get_thread",
            args_model=PostfachGetThreadArgs,
            is_mutating=False,
            handler=_postfach_get_thread_handler,
        ),
        "postfach_draft_reply": ToolSpec(
            name="postfach_draft_reply",
            args_model=PostfachDraftReplyArgs,
            is_mutating=True,
            handler=_postfach_draft_reply_handler,
        ),
        "postfach_send_draft": ToolSpec(
            name="postfach_send_draft",
            args_model=PostfachSendDraftArgs,
            is_mutating=True,
            handler=_postfach_send_draft_handler,
        ),
        "postfach_link_entities": ToolSpec(
            name="postfach_link_entities",
            args_model=PostfachLinkEntitiesArgs,
            is_mutating=True,
            handler=_postfach_link_entities_handler,
        ),
        "postfach_extract_structured": ToolSpec(
            name="postfach_extract_structured",
            args_model=PostfachExtractStructuredArgs,
            is_mutating=True,
            handler=_postfach_extract_structured_handler,
        ),
        "postfach_extract_intake": ToolSpec(
            name="postfach_extract_intake",
            args_model=PostfachExtractIntakeArgs,
            is_mutating=True,
            handler=_postfach_extract_intake_handler,
        ),
        "postfach_create_followup": ToolSpec(
            name="postfach_create_followup",
            args_model=PostfachCreateFollowupArgs,
            is_mutating=True,
            handler=_postfach_create_followup_handler,
        ),
        "postfach_create_lead_from_thread": ToolSpec(
            name="postfach_create_lead_from_thread",
            args_model=PostfachCreateLeadFromThreadArgs,
            is_mutating=True,
            handler=_postfach_create_lead_from_thread_handler,
        ),
        "postfach_create_case_from_thread": ToolSpec(
            name="postfach_create_case_from_thread",
            args_model=PostfachCreateCaseFromThreadArgs,
            is_mutating=True,
            handler=_postfach_create_case_from_thread_handler,
        ),
        "postfach_create_tasks_from_thread": ToolSpec(
            name="postfach_create_tasks_from_thread",
            args_model=PostfachCreateTasksFromThreadArgs,
            is_mutating=True,
            handler=_postfach_create_tasks_from_thread_handler,
        ),
    }
    # Dot aliases for forward compatibility with tool-call conventions.
    specs["postfach.extract_intake"] = specs["postfach_extract_intake"]
    specs["postfach.create_lead_from_thread"] = specs[
        "postfach_create_lead_from_thread"
    ]
    specs["postfach.create_case_from_thread"] = specs[
        "postfach_create_case_from_thread"
    ]
    specs["postfach.create_tasks_from_thread"] = specs[
        "postfach_create_tasks_from_thread"
    ]
    return specs


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_contacts": ToolSpec(
        name="search_contacts",
        args_model=SearchContactsArgs,
        is_mutating=False,
        handler=_search_contacts_handler,
    ),
    "search_documents": ToolSpec(
        name="search_documents",
        args_model=SearchDocumentsArgs,
        is_mutating=False,
        handler=_search_documents_handler,
    ),
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
    **_postfach_specs(),
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "search_contacts": "Sucht Kontakte (Name, E-Mail, Rolle, Kunde).",
    "search_documents": "Durchsucht redigierte Knowledge-Dokumente per Volltext.",
    "create_task": "Erstellt einen neuen Task.",
}


def dispatch(
    name: str,
    args_dict: dict[str, Any],
    *,
    read_only_flag: bool,
    tenant_id: str,
    user: str,
) -> dict[str, Any]:
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


def ollama_tool_definitions(
    *, allowed_names: list[str] | None = None
) -> list[dict[str, Any]]:
    names = (
        [str(name) for name in allowed_names]
        if allowed_names
        else sorted(TOOL_REGISTRY.keys())
    )
    out: list[dict[str, Any]] = []
    for name in names:
        tool = TOOL_REGISTRY.get(name)
        if tool is None:
            continue
        schema = tool.args_model.model_json_schema()
        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": TOOL_DESCRIPTIONS.get(name, f"Tool: {name}"),
                    "parameters": schema,
                },
            }
        )
    return out
