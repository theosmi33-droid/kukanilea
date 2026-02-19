from __future__ import annotations

import json
import os
from typing import Any

from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

from .memory import list_recent_conversations, save_conversation
from .ollama_client import DEFAULT_OLLAMA_MODEL, ollama_chat, ollama_is_available
from .queue import llm_queue
from .tools import execute_tool, ollama_tools

MAX_TOOL_CALLS_PER_TURN = 3
MAX_TOOL_ROUNDS = 2

SYSTEM_PROMPT = (
    "Du bist der lokale KUKANILEA-Assistent. "
    "Nutze nur erlaubte Tools. "
    "Kein SQL, keine Secrets, keine Systemdateien. "
    "Bei Unsicherheit stelle Rueckfragen. "
    "Wenn Tools genutzt werden, fuehre sie praezise aus und antworte danach knapp."
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


def process_message(
    *,
    tenant_id: str,
    user_id: str,
    user_message: str,
    read_only: bool,
) -> dict[str, Any]:
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    message_clean = str(user_message or "").strip()
    if not message_clean:
        return {
            "status": "error",
            "response": "Bitte eine Nachricht eingeben.",
            "conversation_id": None,
            "tool_used": [],
        }

    if not ollama_is_available():
        return {
            "status": "ai_disabled",
            "response": (
                "KI-Assistent ist nicht verfuegbar (Ollama offline). "
                "Starte lokal mit `ollama serve`."
            ),
            "conversation_id": None,
            "tool_used": [],
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

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history_msgs,
        {"role": "user", "content": message_clean},
    ]
    tools = ollama_tools()
    used_tools: list[str] = []
    final_text = ""

    for _round in range(MAX_TOOL_ROUNDS + 1):
        response = llm_queue.run(
            ollama_chat,
            messages=messages,
            model=model,
            tools=tools,
            timeout_s=90,
        )
        message_obj = response.get("message")
        if not isinstance(message_obj, dict):
            final_text = "KI-Antwort ungueltig."
            break

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

        for call in tool_calls[:MAX_TOOL_CALLS_PER_TURN]:
            tool_name = str(call.get("name") or "").strip()
            args = call.get("args")
            args_dict = args if isinstance(args, dict) else {}
            outcome = execute_tool(
                name=tool_name,
                args=args_dict,
                tenant_id=tenant_id,
                user_id=user_id,
                read_only=read_only,
            )
            used_tools.append(tool_name)
            tool_payload = {
                "name": tool_name,
                "result": outcome.get("result") or {},
                "error": outcome.get("error"),
            }
            messages.append(
                {
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(tool_payload, ensure_ascii=False),
                }
            )
        else:
            continue
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

    try:
        event_append(
            event_type="ai_conversation",
            entity_type="ai_conversation",
            entity_id=entity_id_int(conversation_id),
            payload={
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "tool_count": len(used_tools),
            },
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "response": final_text,
        "conversation_id": conversation_id,
        "tool_used": [tool for tool in used_tools if tool],
    }
