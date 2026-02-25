from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from flask import current_app, has_app_context

from app.auth import current_tenant, current_user

from . import llm_ollama, prompts, retrieval_fts, tools


def _facts_only_text(facts: List[Dict[str, Any]]) -> str:
    if not facts:
        return "Ich habe lokal keine passenden Fakten gefunden."
    lines = ["Ich habe lokal folgende Fakten gefunden:"]
    for fact in facts[:6]:
        lines.append(f"- {fact.get('text', '')}")
    return "\n".join(lines)


def _frozen_response(
    *,
    text: str,
    facts: List[Dict[str, Any]],
    action: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {"text": text, "facts": facts, "action": action}


def _try_parse_action(raw: str) -> Optional[Dict[str, Any]]:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
    except Exception:
        # try extract first json object from mixed text
        start = s.find("{")
        end = s.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            obj = json.loads(s[start : end + 1])
        except Exception:
            return None
    if not isinstance(obj, dict):
        return None
    if "action" not in obj:
        return None
    action_name = obj.get("action")
    args = obj.get("args") or {}
    if not isinstance(action_name, str) or not isinstance(args, dict):
        return None
    return {"action": action_name, "args": args}


def answer(user_msg: str) -> Dict[str, Any]:
    try:
        msg = (user_msg or "").strip()
        if not msg:
            return _frozen_response(
                text="Bitte gib eine Nachricht ein.", facts=[], action=None
            )

        retrieval_fts.process_queue(limit=200)
        facts = retrieval_fts.search(msg, limit=6)

        prompt = prompts.build_prompt(msg, facts)
        raw = llm_ollama.generate(prompt)
        if raw is None:
            return _frozen_response(
                text=_facts_only_text(facts), facts=facts, action=None
            )

        parsed = _try_parse_action(raw)
        if not parsed:
            return _frozen_response(
                text=raw.strip() or _facts_only_text(facts), facts=facts, action=None
            )

        from flask import has_request_context
        tenant_id = current_tenant() if has_request_context() else ""
        user = current_user() if has_request_context() else "system"
        read_only = (
            bool(current_app.config.get("READ_ONLY", False))
            if has_app_context()
            else False
        )

        dispatch_result = tools.dispatch(
            parsed["action"],
            parsed["args"],
            read_only_flag=read_only,
            tenant_id=tenant_id,
            user=user,
        )

        action = {
            "name": parsed["action"],
            "args": parsed["args"],
            "result": dispatch_result.get("result") or {},
            "error": dispatch_result.get("error"),
        }

        if action["error"]:
            text = f"Aktion fehlgeschlagen: {action['error']['msg']}"
        else:
            text = f"Aktion {action['name']} erfolgreich ausgefuehrt."

        return _frozen_response(text=text, facts=facts, action=action)

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return _frozen_response(
            text=f"Interner Fehler, ich antworte nur mit Fakten. ({exc.__class__.__name__})",
            facts=[],
            action=None,
        )
