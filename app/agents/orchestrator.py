from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from app.agents.archive import ArchiveAgent
from app.agents.auth_tenant import AuthTenantAgent
from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.customer import CustomerAgent
from app.agents.executor import AgentExecutor
from app.agents.guards import build_safe_suggestions, detect_prompt_injection
from app.agents.index import IndexAgent
from app.agents.llm import LLMProvider, get_default_provider
from app.agents.mail import MailAgent
from app.agents.memory import MemoryAgent
from app.agents.memory_store import MemoryManager
from app.agents.mesh import MeshAgent
from app.agents.observer import ObserverAgent
from app.agents.open_file import OpenFileAgent
from app.agents.planner import Planner
from app.agents.review import ReviewAgent
from app.agents.search import SearchAgent
from app.agents.summary import SummaryAgent
from app.agents.upload import UploadAgent
from app.agents.weather import WeatherAgent

from .intent import IntentParser
from .policy import PolicyEngine
from .tool_registry import ToolRegistry

logger = logging.getLogger("kukanilea.agents.messenger")


@dataclass
class OrchestratorResult:
    text: str
    actions: List[Dict[str, Any]]
    intent: str
    data: Dict[str, Any]
    suggestions: List[str]
    ok: bool = True
    error: str | None = None
    audit: Dict[str, Any] = field(default_factory=dict)


class MessengerAgent(BaseAgent):
    name = "messenger"
    required_role = "USER"
    scope = "messenger"
    tools = [
        "messenger.message.send",
        "messenger.sync.poll",
        "messenger.status.check",
        "tasks.item.create",
        "calendar.event.create",
        "docs.search.query",
        "mail.draft.generate",
    ]

    def __init__(self, core_module=None) -> None:
        self.core = core_module
        self.planner = Planner()
        self.executor = AgentExecutor()

    def can_handle(self, intent: str, message: str) -> bool:
        text = (message or "").lower()
        tokens = [
            "telegram",
            "whatsapp",
            "instagram",
            "messenger",
            "teamchat",
            "intern",
            "nachricht",
            "@kukanilea",
        ]
        return any(t in text for t in tokens) or intent == "messenger"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        text = message.strip()
        provider = self._extract_provider(text)
        crm_match = self._crm_match_hint(text)
        memory = self._get_memory_manager(context)
        stored = False
        if memory:
            stored = memory.store_messenger_message(
                tenant_id=context.tenant_id,
                provider=provider,
                sender=context.user,
                recipient="team",
                content=text,
                crm_match=crm_match,
                direction="inbound",
            )

        if "@kukanilea" in text.lower() or len(text.split()) > 10:
            return self._run_agentic_loop(text, intent, context, provider, stored, crm_match)

        actions: List[Dict[str, Any]] = []
        if self._asks_for_search(text):
            actions.append({"type": "docs.search.query", "query": text})
        proposals = self._build_proposals(text, provider, crm_match)
        hint_lines = [
            "Messenger-Hub (Agent-Mode) aktiv.",
            f"Provider: {provider.upper()}.",
        ]
        if crm_match:
            hint_lines.append(f"CRM-Match: {crm_match.get('display')}")
        if proposals:
            hint_lines.append(f"{len(proposals)} Aktionsvorschläge erstellt (Confirm-Gate benötigt).")

        return AgentResult(
            text="\n".join(hint_lines),
            actions=actions,
            data={
                "hub": {
                    "provider": provider,
                    "crm_match": crm_match,
                    "proposals": proposals,
                    "react_trace": [
                        {
                            "thought": f"Einfache Nachricht erkannt (Provider: {provider}). Speicherstatus: {stored}",
                            "action": "none",
                            "observation": {"mode": "heuristic"}
                        }
                    ],
                    "storage_ok": stored,
                    "mode": "heuristic"
                }
            },
            suggestions=["zeige provider status", "suche nachricht", "erstelle task"]
        )

    def _run_agentic_loop(self, message: str, intent: str, context: AgentContext, provider: str, stored: bool, crm_match: Dict[str, Any], max_steps: int = 4) -> AgentResult:
        history = []
        final_answer = ""
        actions: List[Dict[str, Any]] = []
        for i in range(max_steps):
            plan = self.planner.plan(intent, message, tenant_id=context.tenant_id, history=history)
            if not plan: break
            tool_name = plan.get("tool")
            # Map legacy tool names if they appear in plan
            tool_name = self._map_legacy_tool(tool_name)
            params = plan.get("params", {})
            thought = plan.get("thought", "")
            if tool_name == "final_answer":
                final_answer = params.get("answer", thought)
                break
            try:
                observation = self.executor.execute(tool_name, params)
                history.append({"thought": thought, "action": tool_name, "params": params, "observation": observation})
                if tool_name in ["tasks.item.create", "calendar.event.create", "mail.draft.generate", "messenger.message.send"]:
                    actions.append({"type": tool_name, **params})
            except Exception as e:
                history.append({"thought": thought, "action": tool_name, "params": params, "observation": {"error": str(e)}})
        
        return AgentResult(
            text=final_answer or f"Ich habe die Nachricht analysiert ({len(history)} Schritte).",
            actions=actions,
            data={"hub": {"provider": provider, "crm_match": crm_match, "react_trace": history, "storage_ok": stored, "mode": "agentic_loop"}},
            suggestions=["was hast du getan?", "zeige details", "ok"]
        )

    def _map_legacy_tool(self, tool: str | None) -> str:
        mapping = {
            "messenger_send": "messenger.message.send",
            "messenger_sync": "messenger.sync.poll",
            "messenger_status": "messenger.status.check",
            "create_task": "tasks.item.create",
            "create_appointment": "calendar.event.create",
            "search_docs": "docs.search.query",
            "mail_generate": "mail.draft.generate",
        }
        return mapping.get(str(tool), str(tool))

    def _extract_provider(self, message: str) -> str:
        text = message.lower()
        if "telegram" in text: return "telegram"
        if "instagram" in text: return "instagram"
        if "whatsapp" in text: return "whatsapp"
        if any(k in text for k in ["meta", "facebook", "messenger"]): return "meta"
        return "internal"

    def _crm_match_hint(self, message: str) -> Dict[str, str]:
        phone_match = re.search(r"(\+?\d[\d\-\s]{7,}\d)", message)
        if phone_match:
            return {"source": "phone", "display": f"Kunde (Tel: {phone_match.group(1).strip()})", "confidence": "medium"}
        return {}

    def _get_memory_manager(self, context: AgentContext) -> MemoryManager | None:
        if not self.core:
            db_path = context.meta.get("db_path")
            return MemoryManager(db_path) if db_path else None
        auth_db = getattr(self.core, "AUTH_DB", None) or getattr(self.core, "DB_PATH", None)
        return MemoryManager(str(auth_db)) if auth_db else None

    def _build_proposals(self, text: str, provider: str, crm_match: Dict[str, Any]) -> List[Dict[str, Any]]:
        proposals = []
        text_lower = text.lower()
        if any(k in text_lower for k in ["sende", "schick", "antworten", "reply"]):
            proposals.append({"type": "messenger.message.send", "provider": provider, "confirm_required": True, "policy": "business_only" if provider in ["whatsapp", "meta", "instagram"] else "standard"})
        if any(k in text_lower for k in ["task", "aufgabe", "todo"]):
            proposals.append({"type": "tasks.item.create", "confirm_required": True, "title": text[:50] + "..."})
        if any(k in text_lower for k in ["termin", "kalender", "meeting"]):
            proposals.append({"type": "calendar.event.create", "confirm_required": True, "summary": text[:50] + "..."})
        if any(k in text_lower for k in ["entwurf", "draft", "mail"]):
            proposals.append({"type": "mail.draft.generate", "confirm_required": True, "reason": "assistant_draft"})
        return proposals

    def _asks_for_search(self, text: str) -> bool:
        return any(k in text.lower() for k in ["suche", "finde", "dokument", "rechnung"])


class Orchestrator:
    def __init__(
        self, core_module, weather_adapter=None, llm_provider: LLMProvider | None = None
    ) -> None:
        self.core = core_module
        self.llm = llm_provider or get_default_provider()
        self.intent_parser = IntentParser(self.llm)
        self.policy = PolicyEngine()
        self.tools = ToolRegistry()
        self.audit_log = getattr(core_module, "audit_log", None)
        self.task_create = getattr(core_module, "task_create", None)
        self.allowed_tools = {
            "docs.search.query",
            "docs.file.open",
            "crm.customer.show",
            "docs.file.summarize",
            "tasks.list.query",
            "sys.index.rebuild",
            "fin.lexoffice.upload",
            "sys.memory.store",
            "sys.memory.search",
            "fin.zugferd.generate",
            "sys.mesh.sync",
            "mail.draft.generate",
            "time.entry.start",
            "time.entry.stop",
            "time.project.create",
            "projects.job.create",
            "projects.task.assign",
        }
        self.agents = [
            OpenFileAgent(),
            SearchAgent(core_module),
            CustomerAgent(core_module),
            SummaryAgent(core_module, llm_provider=self.llm),
            UploadAgent(),
            ReviewAgent(),
            ArchiveAgent(),
            IndexAgent(core_module),
            MailAgent(),
            MemoryAgent(),
            MessengerAgent(core_module),
            MeshAgent(),
            WeatherAgent(weather_adapter),
            AuthTenantAgent(),
            ObserverAgent(),
        ]
        for agent in self.agents:
            for tool in agent.tools:
                self.tools.register(tool, agent.name)

    def handle(self, message: str, context: AgentContext) -> OrchestratorResult:
        # Add db_path for agents that need direct DB access (like MemoryStore in MessengerAgent)
        auth_db = getattr(self.core, "AUTH_DB", None) or getattr(self.core, "DB_PATH", None)
        if auth_db:
            context.meta["db_path"] = str(auth_db)

        safe_mode = bool(context.meta.get("safe_mode"))
        intent_result = self.intent_parser.parse(message, allow_llm=not safe_mode)
        intent = intent_result.intent
        injection, reasons = detect_prompt_injection(message)
        if injection:
            self._record_failure(
                context,
                action="prompt_injection_blocked",
                target=message,
                meta={"intent": intent, "reasons": reasons},
            )
            suggestions = build_safe_suggestions(
                ["suche rechnung", "wer ist 12393", "öffne <token>"]
            )
            return OrchestratorResult(
                text="Diese Anfrage wurde aus Sicherheitsgründen blockiert. Bitte formuliere eine normale Such- oder Kundenanfrage.",
                actions=[],
                intent=intent,
                data={"error": "prompt_injection_blocked"},
                suggestions=suggestions,
                ok=False,
                error="prompt_injection_blocked",
                audit={
                    "event_type": "action.sys.security.blocked",
                    "risk_level": "L2"
                }
            )

        for agent in self.agents:
            if agent.can_handle(intent, message):
                if not self.policy.allows(context.role, agent.required_role):
                    self._record_failure(
                        context,
                        action="policy_denied",
                        target=agent.name,
                        meta={"intent": intent, "required_role": agent.required_role},
                    )
                    return OrchestratorResult(
                        text="Keine Berechtigung für diese Aktion.",
                        actions=[],
                        intent=intent,
                        data={"error": "policy_denied"},
                        suggestions=build_safe_suggestions(["hilfe", "suche rechnung"]),
                        ok=False,
                        error="policy_denied",
                        audit={
                            "event_type": "action.sys.auth.denied",
                            "risk_level": "L0"
                        }
                    )
                result: AgentResult = agent.handle(message, intent, context)
                actions = self._apply_policy(context, agent, result.actions)
                
                # Standardize Audit Envelope
                audit_meta = {
                    "event_type": f"action.{agent.scope}.handle.ok",
                    "risk_level": "L0" if not actions else "L1"
                }
                if any(a.get("confirm_required") for a in actions):
                    audit_meta["risk_level"] = "L2"

                return OrchestratorResult(
                    text=result.text,
                    actions=actions,
                    intent=intent,
                    data=result.data,
                    suggestions=build_safe_suggestions(result.suggestions),
                    ok=result.error is None,
                    error=result.error,
                    audit=audit_meta
                )

        self._record_failure(
            context,
            action="intent_unhandled",
            target=message,
            meta={"intent": intent},
        )
        return OrchestratorResult(
            text="Ich bin mir nicht sicher. Formuliere bitte konkreter (z.B. 'suche Rechnung KDNR 123').",
            actions=[],
            intent=intent,
            data={"error": "intent_unhandled"},
            suggestions=build_safe_suggestions(["suche rechnung", "wer ist 12393"]),
            ok=False,
            error="intent_unhandled",
            audit={
                "event_type": "action.sys.intent.unhandled",
                "risk_level": "L0"
            }
        )

    def _apply_policy(
        self, context: AgentContext, agent, actions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        agent_tool_set = set(agent.tools or [])
        allowlisted_agent_tools = agent_tool_set.intersection(self.allowed_tools)
        if agent_tool_set and not allowlisted_agent_tools:
            self._record_failure(
                context,
                action="tool_not_allowlisted",
                target=",".join(sorted(agent_tool_set)),
                meta={"intent": agent.name},
            )
            return []
        for action in actions or []:
            action_type = action.get("type", "")
            if not action_type or action_type not in self.allowed_tools:
                self._record_failure(
                    context,
                    action="tool_not_allowlisted",
                    target=str(action_type),
                    meta={"intent": agent.name},
                )
                continue
            registered_agents = self.tools.list_tools().get(action_type, [])
            if agent.name not in registered_agents or action_type not in agent_tool_set:
                self._record_failure(
                    context,
                    action="tool_registry_mismatch",
                    target=str(action_type),
                    meta={"intent": agent.name},
                )
                continue
            if not self.policy.policy_check(
                context.role, context.tenant_id, action_type, agent.scope
            ):
                self._record_failure(
                    context,
                    action="tool_policy_denied",
                    target=str(action_type),
                    meta={"intent": agent.name},
                )
                continue
            filtered.append(action)
            if callable(self.audit_log):
                self.audit_log(
                    user=context.user,
                    role=context.role,
                    action=action.get("type", ""),
                    target=str(action.get("token", "") or action.get("target", "")),
                    meta={"intent": agent.name, "scope": agent.scope},
                    tenant_id=context.tenant_id,
                )
        return filtered

    def _record_failure(
        self, context: AgentContext, action: str, target: str, meta: Dict[str, Any]
    ) -> None:
        if callable(self.audit_log):
            self.audit_log(
                user=context.user,
                role=context.role,
                action=action,
                target=str(target)[:256],
                meta=meta,
                tenant_id=context.tenant_id,
            )
        if callable(self.task_create):
            self.task_create(
                tenant=context.tenant_id or "default",
                severity="WARN",
                task_type="SECURITY" if "prompt_injection" in action else "POLICY",
                title=f"Orchestrator blocked action: {action}",
                details=str(target)[:500],
                meta=meta,
                created_by=context.user or "",
            )


def answer(user_msg: str, role: str | None = None) -> Dict[str, Any]:
    """Top-level entry point for the agentic chat."""
    from app import core
    from app.auth import current_role, current_tenant, current_user

    # Simple adapter for the weather if present
    _weather_adapter = None
    try:
        from app.web import get_weather_info
        _weather_adapter = get_weather_info
    except ImportError:
        pass

    orchestrator = Orchestrator(core, weather_adapter=_weather_adapter)

    context = AgentContext(
        tenant_id=current_tenant() or "default",
        user=str(current_user() or "dev"),
        role=str(role or current_role() or "USER"),
    )

    res = orchestrator.handle(user_msg, context)

    return {
        "text": res.text,
        "actions": res.actions,
        "intent": res.intent,
        "suggestions": res.suggestions,
        "ok": res.ok,
        "error": res.error
    }
