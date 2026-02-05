from __future__ import annotations

from .base import AgentContext, AgentResult, BaseAgent


class WeatherAgent(BaseAgent):
    name = "weather"
    required_role = "READONLY"
    scope = "weather"
    tools = ["weather"]

    def __init__(self, weather_adapter=None) -> None:
        self.weather_adapter = weather_adapter

    def can_handle(self, intent: str, message: str) -> bool:
        return intent == "weather"

    def handle(self, message: str, intent: str, context: AgentContext) -> AgentResult:
        if callable(self.weather_adapter):
            return AgentResult(text=str(self.weather_adapter(message)))
        return AgentResult(text="Wetter-Integration ist aktuell deaktiviert.")
