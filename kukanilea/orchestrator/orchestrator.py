from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from kukanilea.agents import (
    AgentContext,
    AgentResult,
    ArchiveAgent,
    AuthTenantAgent,
    CustomerAgent,
    IndexAgent,
    MailAgent,
    OpenFileAgent,
    ReviewAgent,
    SearchAgent,
    SummaryAgent,
    UIAgent,
    UploadAgent,
    WeatherAgent,
)
from kukanilea.llm import LLMProvider, MockProvider, get_default_provider
from .intent import IntentParser
from .policy import PolicyEngine
from .tool_registry import ToolRegistry


@dataclass
class OrchestratorResult:
    text: str
    actions: List[Dict[str, Any]]
    intent: str
    data: Dict[str, Any]


class Orchestrator:
    def __init__(self, core_module, weather_adapter=None, llm_provider: LLMProvider | None = None) -> None:
        self.llm = llm_provider or get_default_provider()
        self.intent_parser = IntentParser(self.llm)
        self.policy = PolicyEngine()
        self.tools = ToolRegistry()
        self.audit_log = getattr(core_module, "audit_log", None)
        self.allowed_tools = {
            "search_docs",
            "open_doc",
            "show_customer",
            "summarize_doc",
            "list_tasks",
            "rebuild_index",
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
            WeatherAgent(weather_adapter),
            AuthTenantAgent(),
        ]
        for agent in self.agents:
            for tool in agent.tools:
                self.tools.register(tool, agent.name)

    def handle(self, message: str, context: AgentContext) -> OrchestratorResult:
        intent_result = self.intent_parser.parse(message)
        intent = intent_result.intent

        for agent in self.agents:
            if agent.can_handle(intent, message):
                if not self.policy.allows(context.role, agent.required_role):
                    return OrchestratorResult(
                        text="Keine Berechtigung für diese Aktion.",
                        actions=[],
                        intent=intent,
                        data={},
                    )
                result: AgentResult = agent.handle(message, intent, context)
                actions = self._apply_policy(context, agent, result.actions)
                return OrchestratorResult(
                    text=result.text,
                    actions=actions,
                    intent=intent,
                    data=result.data,
                )

        return OrchestratorResult(
            text="Ich bin mir nicht sicher. Formuliere bitte konkreter (z.B. 'suche Rechnung KDNR 123').",
            actions=[],
            intent=intent,
            data={},
        )

    def _apply_policy(self, context: AgentContext, agent, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        tool_name = agent.tools[0] if agent.tools else ""
        if tool_name and tool_name not in self.allowed_tools:
            return []
        for action in actions or []:
            if not self.policy.policy_check(context.role, context.tenant_id, action.get("type", ""), agent.scope):
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
