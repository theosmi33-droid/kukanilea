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
    MockLLM,
    OpenFileAgent,
    ReviewAgent,
    SearchAgent,
    SummaryAgent,
    UIAgent,
    UploadAgent,
    WeatherAgent,
)
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
    def __init__(self, core_module, weather_adapter=None) -> None:
        self.llm = MockLLM()
        self.intent_parser = IntentParser(self.llm)
        self.policy = PolicyEngine()
        self.tools = ToolRegistry()
        self.agents = [
            OpenFileAgent(),
            SearchAgent(core_module),
            CustomerAgent(core_module),
            SummaryAgent(core_module),
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
                return OrchestratorResult(
                    text=result.text,
                    actions=result.actions,
                    intent=intent,
                    data=result.data,
                )

        return OrchestratorResult(
            text="Ich bin mir nicht sicher. Formuliere bitte konkreter (z.B. 'suche Rechnung KDNR 123').",
            actions=[],
            intent=intent,
            data={},
        )
