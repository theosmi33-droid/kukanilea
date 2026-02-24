from __future__ import annotations

import json
import os
import re
from typing import Any

from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

from .audit import audit_tool_call
from .confirm import sign_confirmation, verify_confirmation
from .memory import list_recent_conversations, save_conversation
from .ollama_client import DEFAULT_OLLAMA_MODEL, ollama_is_available
from .personal_memory import add_user_note, render_user_memory_context
from .provider_router import (
    chat_with_fallback,
    provider_order_from_env,
    provider_specs_from_env,
)
from .queue import llm_queue
from .security import wrap_with_salt
from .tool_policy import validate_tool_call
from .tools import execute_tool, ollama_tools

MAX_TOOL_CALLS_PER_TURN = 3
MAX_TOOL_ROUNDS = 2
CONFIRM_TTL_SECONDS = 300

SYSTEM_PROMPT = (
    "Du bist der lokale KUKANILEA-Assistent für das Handwerk. "
    "SICHERHEIT: Unterstütze niemals kriminelle, betrügerische oder illegale Handlungen. "
    "INTERNE DATEN: Du darfst betriebsinterne Infos (Kunden, Aufträge) nennen, aber keine Manipulationen oder unsaubere Abrechnungen vorschlagen. "
    "FOKUS: Antworte in 1 Satz. Andere Themen: 'Nur Handwerk-Support möglich.'"
)
_MEMORY_CMD_RE = re.compile(
    r"^\s*(?:merke\s*dir|merk\s*dir|remember)\s*:\s*(?P<note>.+?)\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _tool_calls_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls = message.get("tool_calls")
    if not isinstance(calls, list):
        return []
    out: list[dict[str, Any]] = []
    for row in calls:
        if not isinstance(row, dict):
            continue
        fn = row.get("function")
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
            except Exception:
                parsed = {}
        elif isinstance(args, dict):
            parsed = args
        else:
            parsed = {}
        out.append({"name": name, "args": parsed if isinstance(parsed, dict) else {}})
    return out


def _assistant_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    return ""


def _append_conversation_event(
    *, tenant_id: str, conversation_id: str, tool_count: int
) -> None:
    try:
        event_append(
            event_type="ai_conversation",
            entity_type="ai_conversation",
            entity_id=entity_id_int(conversation_id),
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "tool_count": int(tool_count),
            },
        )
    except Exception:
        pass


def process_message(
    *,
    tenant_id: str,
    user_id: str,
    user_message: str,
    read_only: bool,
    role: str | None = None,
) -> dict[str, Any]:
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    providers = provider_order_from_env()
    effective_specs = provider_specs_from_env(
        order=providers, tenant_id=tenant_id, role=role
    )
    message_clean = str(user_message or "").strip()
    if not message_clean:
        return {
            "status": "error",
            "response": "Bitte eine Nachricht eingeben.",
            "conversation_id": None,
            "tool_used": [],
            "pending_confirmation": None,
        }

    memory_match = _MEMORY_CMD_RE.match(message_clean)
    if memory_match is not None:
        note = str(memory_match.group("note") or "").strip()
        if note:
            note_id = add_user_note(
                tenant_id=tenant_id,
                user_id=user_id,
                note=note,
                source="chat_command",
            )
            final_text = "Verstanden. Ich habe mir das fuer dich gemerkt."
            conversation_id = save_conversation(
                tenant_id=tenant_id,
                user_id=user_id,
                user_message=message_clean,
                assistant_response=final_text,
                tools_used=["personal_memory.save"],
            )
            _append_conversation_event(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                tool_count=1,
            )
            return {
                "status": "ok",
                "response": final_text,
                "conversation_id": conversation_id,
                "tool_used": ["personal_memory.save"],
                "pending_confirmation": None,
                "provider": "local_memory",
                "memory_note_id": note_id,
            }

    if not effective_specs:
        return {
            "status": "ai_disabled",
            "response": (
                "KI-Assistent ist fuer Rolle/Mandant nicht freigeschaltet. "
                "Bitte AI-Policy pruefen."
            ),
            "conversation_id": None,
            "tool_used": [],
        }

    if (
        len(effective_specs) == 1
        and str(effective_specs[0].provider_type).strip().lower() == "ollama"
        and not ollama_is_available()
    ):
        return {
            "status": "ai_disabled",
            "response": (
                "KI-Assistent ist nicht verfuegbar (Ollama offline). "
                "Starte lokal mit `ollama serve`."
            ),
            "conversation_id": None,
            "tool_used": [],
            "pending_confirmation": None,
        }

    history = list_recent_conversations(tenant_id=tenant_id, user_id=user_id, limit=3)
    history_msgs: list[dict[str, str]] = []
    for item in reversed(history):
        user_text = str(item.get("user_message") or "").strip()
        assistant_text = str(item.get("assistant_response") or "").strip()
        if user_text:
            history_msgs.append({"role": "user", "content": user_text[:800]})
        if assistant_text:
            history_msgs.append({"role": "assistant", "content": assistant_text[:1200]})

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    personal_context = render_user_memory_context(
        tenant_id=tenant_id,
        user_id=user_id,
        limit=8,
        max_chars=1400,
    )
    if personal_context:
        messages.append({"role": "system", "content": personal_context})
    messages.extend(history_msgs)

    # EPIC 7: Salted Sequence Tags integration
    # Wrap user input to prevent prompt injection
    salted_user_msg = wrap_with_salt(
        instruction="Benutzereingabe für die Verarbeitung:",
        user_input=message_clean
    )
    messages.append({"role": "user", "content": salted_user_msg})

    tools = ollama_tools()
    used_tools: list[str] = []
    final_text = ""
    status = "ok"
    pending_confirmation: dict[str, Any] | None = None
    provider_used = ""
    first_round = True

    for _round in range(MAX_TOOL_ROUNDS + 1):
        queued = llm_queue.run(
            chat_with_fallback,
            messages=messages,
            model=model,
            tools=tools,
            timeout_s=90,
            tenant_id=tenant_id,
            role=role,
        )
        if isinstance(queued, dict) and "response" in queued:
            response = queued.get("response")
            provider_used = str(queued.get("provider") or provider_used)
        else:
            # Backward-compatible path for tests monkeypatching llm_queue.run.
            response = queued if isinstance(queued, dict) else None
            provider_used = provider_used or "ollama"

        if not isinstance(response, dict):
            if first_round:
                return {
                    "status": "ai_disabled",
                    "response": (
                        "KI-Assistent ist derzeit nicht verfuegbar. "
                        "Bitte lokalen/externen Provider pruefen."
                    ),
                    "conversation_id": None,
                    "tool_used": [],
                    "pending_confirmation": None,
                }
            final_text = "KI-Antwort ungueltig."
            status = "error"
            break

        message_obj = response.get("message")
        if not isinstance(message_obj, dict):
            final_text = "KI-Antwort ungueltig."
            status = "error"
            break
        first_round = False

        assistant_text = _assistant_content(message_obj)
        tool_calls = _tool_calls_from_message(message_obj)
        if not tool_calls:
            final_text = assistant_text or "Keine Antwort."
            break

        messages.append(
            {
                "role": "assistant",
                "content": assistant_text,
                "tool_calls": message_obj.get("tool_calls") or [],
            }
        )

        stop_tool_round = False
        for call in tool_calls[:MAX_TOOL_CALLS_PER_TURN]:
            tool_name = str(call.get("name") or "").strip()
            args = call.get("args")
            args_dict = args if isinstance(args, dict) else {}
            try:
                decision = validate_tool_call(tool_name, args_dict)
            except ValueError as exc:
                audit_tool_call(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    tool_name=tool_name,
                    args=args_dict,
                    decision="rejected",
                    status="validation_error",
                    detail=str(exc),
                )
                messages.append(
                    {
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(
                            {
                                "name": tool_name,
                                "result": {},
                                "error": {
                                    "code": "policy_rejected",
                                    "msg": "Tool-Aufruf nicht erlaubt oder ungueltig.",
                                },
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
                continue

            used_tools.append(decision.tool_name)
            if decision.requires_confirm:
                if read_only:
                    audit_tool_call(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        tool_name=decision.tool_name,
                        args=decision.args,
                        decision="blocked",
                        status="read_only",
                        detail="mutation_in_read_only",
                    )
                    final_text = "Diese Aktion aendert Daten und ist im Read-only-Modus deaktiviert."
                    status = "error"
                    stop_tool_round = True
                    break

                token = sign_confirmation(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    tool_name=decision.tool_name,
                    args=decision.args,
                    ttl_seconds=CONFIRM_TTL_SECONDS,
                )
                pending_confirmation = {
                    "tool_name": decision.tool_name,
                    "args": decision.args,
                    "token": token,
                    "expires_in_seconds": CONFIRM_TTL_SECONDS,
                }
                audit_tool_call(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    tool_name=decision.tool_name,
                    args=decision.args,
                    decision="confirmation_required",
                    status="pending",
                )
                final_text = (
                    f"Bestaetigung erforderlich fuer Tool '{decision.tool_name}'. "
                    "Bitte bestaetige den Aufruf explizit."
                )
                status = "confirmation_required"
                stop_tool_round = True
                break

            outcome = execute_tool(
                name=decision.tool_name,
                args=decision.args,
                tenant_id=tenant_id,
                user_id=user_id,
                read_only=read_only,
            )
            error = outcome.get("error")
            audit_tool_call(
                tenant_id=tenant_id,
                user_id=user_id,
                tool_name=decision.tool_name,
                args=decision.args,
                decision="executed",
                status="error" if error else "ok",
                detail=str((error or {}).get("code") or "")
                if isinstance(error, dict)
                else "",
            )
            tool_payload = {
                "name": decision.tool_name,
                "result": outcome.get("result") or {},
                "error": error,
            }
            messages.append(
                {
                    "role": "tool",
                    "name": decision.tool_name,
                    "content": json.dumps(tool_payload, ensure_ascii=False),
                }
            )

        if stop_tool_round:
            break

    if not final_text:
        final_text = "Keine finale KI-Antwort verfuegbar."

    conversation_id = save_conversation(
        tenant_id=tenant_id,
        user_id=user_id,
        user_message=message_clean,
        assistant_response=final_text,
        tools_used=used_tools,
    )
    _append_conversation_event(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        tool_count=len(used_tools),
    )

    return {
        "status": status,
        "response": final_text,
        "conversation_id": conversation_id,
        "tool_used": [tool for tool in used_tools if tool],
        "pending_confirmation": pending_confirmation,
        "provider": provider_used,
    }

async def async_process_message(
    *,
    tenant_id: str,
    user_id: str,
    user_message: str,
    read_only: bool,
    role: str | None = None,
) -> dict[str, Any]:
    """Asynchronous version of process_message for FastAPI concurrency."""
    # We leverage the existing process_message logic but wrap the LLM call
    # This is a wrapper that could be further optimized by making the whole chain async
    return await run_in_threadpool(
        process_message,
        tenant_id=tenant_id,
        user_id=user_id,
        user_message=user_message,
        read_only=read_only,
        role=role
    )

from fastapi.concurrency import run_in_threadpool


def confirm_tool_call(
    *,
    tenant_id: str,
    user_id: str,
    confirmation_token: str,
    read_only: bool,
) -> dict[str, Any]:
    token = str(confirmation_token or "").strip()
    if not token:
        return {
            "status": "error",
            "response": "Bestaetigungstoken fehlt.",
            "conversation_id": None,
            "tool_used": [],
        }

    try:
        payload = verify_confirmation(
            token=token,
            tenant_id=tenant_id,
            user_id=user_id,
            consume=True,
        )
    except ValueError as exc:
        return {
            "status": "error",
            "response": f"Bestaetigung ungueltig: {exc}",
            "conversation_id": None,
            "tool_used": [],
        }

    tool_name = str(payload.get("tool_name") or "").strip()
    args = payload.get("args")
    args_dict = args if isinstance(args, dict) else {}

    try:
        decision = validate_tool_call(tool_name, args_dict)
    except ValueError as exc:
        audit_tool_call(
            tenant_id=tenant_id,
            user_id=user_id,
            tool_name=tool_name,
            args=args_dict,
            decision="confirm_rejected",
            status="validation_error",
            detail=str(exc),
        )
        return {
            "status": "error",
            "response": "Tool-Aufruf nach Bestaetigung ungueltig.",
            "conversation_id": None,
            "tool_used": [tool_name] if tool_name else [],
        }

    if not decision.requires_confirm:
        return {
            "status": "error",
            "response": "Dieses Tool benoetigt keine Bestaetigung.",
            "conversation_id": None,
            "tool_used": [decision.tool_name],
        }

    if read_only:
        audit_tool_call(
            tenant_id=tenant_id,
            user_id=user_id,
            tool_name=decision.tool_name,
            args=decision.args,
            decision="confirm_blocked",
            status="read_only",
        )
        return {
            "status": "error",
            "response": "Read-only-Modus aktiv: Aktion wurde nicht ausgefuehrt.",
            "conversation_id": None,
            "tool_used": [decision.tool_name],
        }

    outcome = execute_tool(
        name=decision.tool_name,
        args=decision.args,
        tenant_id=tenant_id,
        user_id=user_id,
        read_only=read_only,
    )
    error = outcome.get("error")
    if error:
        audit_tool_call(
            tenant_id=tenant_id,
            user_id=user_id,
            tool_name=decision.tool_name,
            args=decision.args,
            decision="confirm_executed",
            status="error",
            detail=str((error or {}).get("code") or "")
            if isinstance(error, dict)
            else "",
        )
        final_text = (
            f"Bestaetigte Aktion '{decision.tool_name}' fehlgeschlagen: "
            f"{(error or {}).get('msg') if isinstance(error, dict) else 'error'}"
        )
        status = "error"
    else:
        audit_tool_call(
            tenant_id=tenant_id,
            user_id=user_id,
            tool_name=decision.tool_name,
            args=decision.args,
            decision="confirm_executed",
            status="ok",
        )
        final_text = f"Bestaetigte Aktion '{decision.tool_name}' wurde ausgefuehrt."
        status = "ok"

    conversation_id = save_conversation(
        tenant_id=tenant_id,
        user_id=user_id,
        user_message=f"[confirm] {decision.tool_name}",
        assistant_response=final_text,
        tools_used=[decision.tool_name],
    )
    _append_conversation_event(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        tool_count=1,
    )

    return {
        "status": status,
        "response": final_text,
        "conversation_id": conversation_id,
        "tool_used": [decision.tool_name],
        "result": outcome.get("result") if isinstance(outcome, dict) else {},
    }
