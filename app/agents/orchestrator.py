from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

from app.agents.archive import ArchiveAgent
from app.agents.auth_tenant import AuthTenantAgent
from app.agents.base import AgentContext, AgentResult
from app.agents.customer import CustomerAgent
from app.agents.guards import build_safe_suggestions, detect_prompt_injection
from app.agents.index import IndexAgent
from app.agents.llm import LLMProvider, get_default_provider
from app.agents.mail import MailAgent
from app.agents.memory import MemoryAgent
from app.agents.memory_store import MemoryManager
from app.agents.mesh import MeshAgent
from app.agents.observer import ObserverAgent
from app.agents.open_file import OpenFileAgent
from app.agents.review import ReviewAgent
from app.agents.search import SearchAgent
from app.agents.summary import SummaryAgent
from app.agents.upload import UploadAgent
from app.agents.weather import WeatherAgent

from .intent import IntentParser
from .policy import PolicyEngine
from .tool_registry import ToolRegistry


@dataclass
class OrchestratorResult:
    text: str
    actions: List[Dict[str, Any]]
    intent: str
    data: Dict[str, Any]
    suggestions: List[str]
    ok: bool = True
    error: str | None = None


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
            "search_docs",
            "open_token",
            "show_customer",
            "summarize_doc",
            "list_tasks",
            "rebuild_index",
            "lexoffice_upload",
            "memory_store",
            "memory_search",
            "generate_zugferd_xml",
            "mesh_sync",
            "mail_generate",
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
            MeshAgent(),
            WeatherAgent(weather_adapter),
            AuthTenantAgent(),
            ObserverAgent(),
        ]
        for agent in self.agents:
            for tool in agent.tools:
                self.tools.register(tool, agent.name)

    def handle(self, message: str, context: AgentContext) -> OrchestratorResult:
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
            )

        if self._is_messenger_request(message):
            return self._handle_messenger_request(message, intent, context)

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
                    )
                result: AgentResult = agent.handle(message, intent, context)
                actions = self._apply_policy(context, agent, result.actions)
                return OrchestratorResult(
                    text=result.text,
                    actions=actions,
                    intent=intent,
                    data=result.data,
                    suggestions=build_safe_suggestions(result.suggestions),
                    ok=result.error is None,
                    error=result.error,
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
        )

    def _is_messenger_request(self, message: str) -> bool:
        text = (message or "").lower()
        messenger_tokens = [
            "telegram",
            "whatsapp",
            "instagram",
            "messenger",
            "teamchat",
            "intern",
            "nachricht",
            "@kukanilea",
        ]
        return any(tok in text for tok in messenger_tokens)

    def _handle_messenger_request(
        self, message: str, intent: str, context: AgentContext
    ) -> OrchestratorResult:
        text = message.strip()
        providers = self._provider_status()
        crm_match = self._crm_match_hint(text)
        extracted = self._extract_provider(text)
        normalized_provider = extracted if extracted != "unknown" else "internal"
        memory = self._memory_manager()
        stored = False
        if memory:
            stored = memory.store_messenger_message(
                tenant_id=context.tenant_id or "default",
                provider=normalized_provider,
                sender=context.user or "unknown",
                recipient="team",
                content=text,
                attachments=[],
                crm_match=crm_match,
                direction="inbound",
                status="stored",
            )

        react_steps = [
            {
                "thought": "Nachricht normalisieren und Provider erkennen.",
                "action": "normalize_message",
                "observation": {"provider": normalized_provider, "stored": stored},
            },
            {
                "thought": "CRM-Heuristik und Folgeaktionen bestimmen.",
                "action": "analyze_context",
                "observation": {"crm_match": crm_match, "intent": intent},
            },
        ]

        actions: List[Dict[str, Any]] = []
        proposals: List[Dict[str, Any]] = []

        if self._asks_for_send(text):
            proposals.append(
                {
                    "type": "send_message",
                    "provider": normalized_provider,
                    "confirm_required": True,
                    "policy_mode": "business_only"
                    if normalized_provider in {"whatsapp", "meta", "instagram"}
                    else "standard",
                }
            )

        if self._asks_for_task(text):
            proposals.append(
                {
                    "type": "create_task",
                    "confirm_required": True,
                    "title": self._extract_task_title(text),
                }
            )

        if self._asks_for_appointment(text):
            proposals.append(
                {
                    "type": "create_appointment",
                    "confirm_required": True,
                    "summary": self._extract_task_title(text),
                }
            )

        if self._asks_for_search(text):
            search_action = {"type": "search_docs", "query": text}
            actions.append(search_action)
            react_steps.append(
                {
                    "thought": "Dokumentkontext für Assistenz vorbereiten.",
                    "action": "search_docs",
                    "observation": {"queued": True},
                }
            )

        if self._asks_for_draft(text):
            proposals.append(
                {
                    "type": "mail_generate",
                    "confirm_required": True,
                    "reason": "assistant_draft",
                }
            )

        hint_lines = [
            "Messenger-Hub aktiv. Interner Chat bleibt offline-fähig.",
            "Externe Provider laufen optional und degraden auf DISCONNECTED, wenn offline.",
        ]
        if crm_match:
            hint_lines.append(
                f"CRM-Match (read-only): {crm_match.get('display', '')}."
            )
        if proposals:
            hint_lines.append(
                "Vorgeschlagene Aktionen sind mit Confirm-Gate markiert und werden nicht automatisch ausgeführt."
            )

        suggestions = build_safe_suggestions(
            [
                "zeige provider status",
                "suche nachricht von <name>",
                "erstelle task aus nachricht",
            ]
        )
        return OrchestratorResult(
            text="\n".join(hint_lines),
            actions=actions,
            intent="messenger",
            data={
                "hub": {
                    "provider_status": providers,
                    "store": {"ok": stored, "mode": "local_memory"},
                    "crm_match": crm_match,
                    "proposals": proposals,
                    "react_trace": react_steps,
                }
            },
            suggestions=suggestions,
            ok=True,
            error=None,
        )

    def _provider_status(self) -> Dict[str, Dict[str, str]]:
        return {
            "internal": {"status": "online", "mode": "offline_always"},
            "telegram": {"status": "disconnected", "mode": "optional"},
            "meta": {"status": "disconnected", "mode": "business_only"},
            "instagram": {"status": "disconnected", "mode": "business_only"},
            "whatsapp": {"status": "future_plugin", "mode": "business_only"},
        }

    def _memory_manager(self) -> MemoryManager | None:
        auth_db = getattr(self.core, "AUTH_DB", None) or getattr(self.core, "DB_PATH", None)
        if not auth_db:
            return None
        return MemoryManager(str(auth_db))

    def _extract_provider(self, message: str) -> str:
        text = (message or "").lower()
        if "telegram" in text:
            return "telegram"
        if "instagram" in text:
            return "instagram"
        if "meta" in text or "facebook" in text or "messenger" in text:
            return "meta"
        if "whatsapp" in text:
            return "whatsapp"
        if "intern" in text or "teamchat" in text:
            return "internal"
        return "unknown"

    def _crm_match_hint(self, message: str) -> Dict[str, str]:
        phone_match = re.search(r"(\+?\d[\d\-\s]{7,}\d)", message or "")
        if phone_match:
            number = phone_match.group(1).strip()
            return {
                "source": "phone",
                "display": f"Kunde mit Telefonnummer {number}",
                "confidence": "medium",
            }
        name_match = re.search(r"\b(kunde|an|von)\s+([A-ZÄÖÜ][a-zäöüß]+)", message or "")
        if name_match:
            return {
                "source": "name",
                "display": f"Kunde {name_match.group(2)}",
                "confidence": "low",
            }
        return {}

    def _asks_for_send(self, message: str) -> bool:
        text = (message or "").lower()
        return any(k in text for k in ["sende", "schick", "antworten", "reply"])

    def _asks_for_task(self, message: str) -> bool:
        text = (message or "").lower()
        return any(k in text for k in ["task", "aufgabe", "todo"])

    def _asks_for_appointment(self, message: str) -> bool:
        text = (message or "").lower()
        return any(k in text for k in ["termin", "kalender", "meeting"])

    def _asks_for_search(self, message: str) -> bool:
        text = (message or "").lower()
        return any(k in text for k in ["suche", "finde", "dokument", "rechnung"])

    def _asks_for_draft(self, message: str) -> bool:
        text = (message or "").lower()
        return any(k in text for k in ["entwurf", "draft", "mail", "email"])

    def _extract_task_title(self, message: str) -> str:
        cleaned = re.sub(r"\s+", " ", (message or "").strip())
        return cleaned[:96] or "Nachricht verarbeiten"

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
