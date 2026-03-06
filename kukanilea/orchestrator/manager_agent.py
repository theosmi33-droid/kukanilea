from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Mapping


CONFIRM_TOKENS = {"1", "true", "yes", "confirm", "ja"}


@dataclass(frozen=True)
class RouteDecision:
    intent: str
    tool: str
    action: str
    requires_confirm: bool = False
    external_call: bool = False


@dataclass
class RouteResult:
    ok: bool
    status: str
    decision: RouteDecision
    reason: str = ""
    confirm_required: bool = False


@dataclass
class EventBus:
    """Minimal EventBus abstraction for orchestrator events."""

    emitter: Callable[[str, dict[str, Any]], None] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "event_type": str(event_type or "unknown"),
            "payload": dict(payload or {}),
        }
        self.events.append(event)
        if callable(self.emitter):
            self.emitter(event["event_type"], event["payload"])


class DeterministicToolRouter:
    """Deterministic mapper for manager-agent routing.

    Critical action routing must remain rule-based and deterministic.
    """

    ROUTES: tuple[tuple[tuple[str, ...], RouteDecision], ...] = (
        (("upload", "datei", "file"), RouteDecision("upload", "upload", "ingest")),
        (("projekt", "project"), RouteDecision("projects", "projects", "list")),
        (("aufgabe", "task", "todo"), RouteDecision("tasks", "tasks", "upsert", requires_confirm=True)),
        (("chat", "messenger", "nachricht"), RouteDecision("messenger", "messenger", "reply", requires_confirm=True, external_call=True)),
        (("mail", "email"), RouteDecision("email", "email", "draft", requires_confirm=True, external_call=True)),
        (("kalender", "termin", "calendar"), RouteDecision("calendar", "calendar", "create", requires_confirm=True)),
        (("zeit", "timer", "time"), RouteDecision("time", "time", "track", requires_confirm=True)),
        (("visual", "report", "analyse"), RouteDecision("visualizer", "visualizer", "render")),
        (("setting", "einstellung", "admin"), RouteDecision("settings", "settings", "update", requires_confirm=True)),
        (("hilfe", "assistant", "chatbot"), RouteDecision("chatbot", "chatbot", "answer")),
        (("dashboard", "status", "health"), RouteDecision("dashboard", "dashboard", "summary")),
    )

    def parse_intent(self, message: str) -> str:
        text = (message or "").strip().lower()
        if not text:
            return "unknown"
        for tokens, decision in self.ROUTES:
            if any(token in text for token in tokens):
                return decision.intent
        return "unknown"

    def select(self, intent: str) -> RouteDecision:
        for _, decision in self.ROUTES:
            if decision.intent == intent:
                return decision
        return RouteDecision(intent="unknown", tool="chatbot", action="fallback")


class ManagerAgent:
    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        audit_logger: Callable[[dict[str, Any]], None] | None = None,
        external_calls_enabled: bool = False,
    ) -> None:
        self.router = DeterministicToolRouter()
        self.event_bus = event_bus or EventBus()
        self.audit_logger = audit_logger
        self.external_calls_enabled = bool(external_calls_enabled)

    def route(self, message: str, context: Mapping[str, Any] | None = None) -> RouteResult:
        ctx = dict(context or {})
        intent = self.router.parse_intent(message)
        decision = self.router.select(intent)

        confirm = _confirm_token(ctx.get("confirm"))
        if decision.requires_confirm and not confirm:
            result = RouteResult(
                ok=False,
                status="confirm_required",
                decision=decision,
                reason="confirm_gate",
                confirm_required=True,
            )
            self._record("manager_agent.confirm_blocked", message, ctx, result)
            return result

        if decision.external_call and not self.external_calls_enabled:
            result = RouteResult(
                ok=False,
                status="offline_blocked",
                decision=decision,
                reason="external_calls_disabled",
            )
            self._record("manager_agent.offline_blocked", message, ctx, result)
            return result

        result = RouteResult(ok=True, status="routed", decision=decision)
        self._record("manager_agent.routed", message, ctx, result)
        return result

    def _record(
        self,
        event_type: str,
        message: str,
        context: Mapping[str, Any],
        result: RouteResult,
    ) -> None:
        payload = {
            "message": str(message or "")[:500],
            "tenant": str(context.get("tenant") or "default"),
            "user": str(context.get("user") or "system"),
            "tool": result.decision.tool,
            "action": result.decision.action,
            "intent": result.decision.intent,
            "status": result.status,
            "ok": result.ok,
            "reason": result.reason,
            "confirm_required": result.confirm_required,
        }
        self.event_bus.emit(event_type, payload)
        if callable(self.audit_logger):
            self.audit_logger(payload)


def _confirm_token(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in CONFIRM_TOKENS
