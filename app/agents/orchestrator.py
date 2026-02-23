from __future__ import annotations

import json
from typing import Any

from flask import current_app, has_app_context

from app.auth import current_tenant, current_user

from . import llm_ollama, prompts, retrieval_fts, tools


def _facts_only_text(facts: list[dict[str, Any]]) -> str:
    if not facts:
        return "Ich habe lokal keine passenden Fakten gefunden."
    lines = ["Ich habe lokal folgende Fakten gefunden:"]
    for fact in facts[:6]:
        lines.append(f"- {fact.get('text', '')}")
    return "\n".join(lines)


def _frozen_response(
    *,
    text: str,
    facts: list[dict[str, Any]],
    action: dict[str, Any] | None,
) -> dict[str, Any]:
    return {"text": text, "facts": facts, "action": action}


def _try_parse_action(raw: str) -> dict[str, Any] | None:
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


def answer(user_msg: str, role: str = "MASTER") -> dict[str, Any]:
    try:
        msg = (user_msg or "").strip()
        if not msg:
            return _frozen_response(
                text="Bitte gib eine Nachricht ein.", facts=[], action=None
            )

        retrieval_fts.process_queue(limit=200)
        facts = retrieval_fts.search(msg, limit=6)

        history: list[str] = []
        executed_actions: set[str] = set()
        max_turns = 3
        final_text = ""
        last_action_result = None

        tenant_id = current_tenant() if has_app_context() else ""
        user = current_user() or "system"
        read_only = (
            bool(current_app.config.get("READ_ONLY", False))
            if has_app_context()
            else False
        )

        for turn in range(max_turns):
            prompt = prompts.build_prompt(msg, facts, history=history, role=role)
            raw = llm_ollama.generate(prompt)
            
            if raw is None:
                if not final_text:
                    final_text = _facts_only_text(facts)
                break

            parsed = _try_parse_action(raw)
            
            if not parsed:
                final_text = raw.strip()
                break
            
            # Action found
            action_name = parsed["action"]
            action_args_str = json.dumps(parsed["args"], sort_keys=True)
            action_key = f"{action_name}:{action_args_str}"

            if action_key in executed_actions:
                history.append(f"System: Loop erkannt! Du hast {action_name} bereits mit diesen Parametern gerufen. Beende jetzt.")
                final_text = "Ich habe mich in einer Wiederholung verfangen und breche sicherheitshalber ab. Bitte stelle deine Frage präziser."
                break
            
            executed_actions.add(action_key)
            history.append(f"Thought: Ich führe {action_name} aus.")
            
            # --- OPENCLAW OBSERVER CHECK ---
            from .observer import ObserverAgent
            observer = ObserverAgent()
            allowed, reason = observer.validate_action(action_name, parsed["args"])
            
            if not allowed:
                history.append(f"Observer: {reason}")
                last_action_result = {
                    "name": action_name,
                    "args": parsed["args"],
                    "result": {},
                    "error": {"code": "boundary_violation", "msg": reason},
                }
                # Wir lassen die KI wissen, dass sie die Grenze erreicht hat
                continue 
            # -------------------------------

            dispatch_result = tools.dispatch(
                parsed["action"],
                parsed["args"],
                read_only_flag=read_only,
                tenant_id=tenant_id,
                user=user,
            )

            last_action_result = {
                "name": parsed["action"],
                "args": parsed["args"],
                "result": dispatch_result.get("result") or {},
                "error": dispatch_result.get("error"),
            }

            if last_action_result["error"]:
                err_msg = f"Fehler bei {action_name}: {last_action_result['error']['msg']}"
                history.append(f"Observation: {err_msg}")
                # We continue to let LLM try to recover or explain
            else:
                success_msg = f"Erfolg: {json.dumps(last_action_result['result'], ensure_ascii=False)}"
                history.append(f"Observation: {success_msg}")

        # Construct final response
        if not final_text:
            if last_action_result:
                final_text = f"Ich habe folgende Aktionen ausgeführt. Letzter Stand: {json.dumps(last_action_result['result'], ensure_ascii=False)}"
            else:
                final_text = _facts_only_text(facts)

        return _frozen_response(text=final_text, facts=facts, action=last_action_result)

    except Exception as exc:
        return _frozen_response(
            text=f"Interner Fehler, ich antworte nur mit Fakten. ({exc.__class__.__name__})",
            facts=[],
            action=None,
        )
