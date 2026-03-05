"""Deterministic AI skill registry with confirm/audit metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

SkillHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    handler: SkillHandler
    read_only: bool = True
    requires_confirm: bool = False
    audit_event: str = "ai_skill_executed"


class SkillsRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register_skill(
        self,
        name: str,
        handler: SkillHandler,
        *,
        read_only: bool = True,
        requires_confirm: bool = False,
        audit_event: str = "ai_skill_executed",
    ) -> SkillDefinition:
        normalized = str(name or "").strip().lower()
        if not normalized:
            raise ValueError("skill_name_required")
        if not callable(handler):
            raise ValueError("skill_handler_must_be_callable")
        # Non-negotiable: write-like skills always require confirm.
        effective_requires_confirm = bool(requires_confirm or not read_only)
        definition = SkillDefinition(
            name=normalized,
            handler=handler,
            read_only=bool(read_only),
            requires_confirm=effective_requires_confirm,
            audit_event=str(audit_event or "ai_skill_executed"),
        )
        self._skills[normalized] = definition
        return definition

    def get(self, name: str) -> SkillDefinition | None:
        return self._skills.get(str(name or "").strip().lower())

    def list_skills(self) -> list[SkillDefinition]:
        return [self._skills[name] for name in sorted(self._skills.keys())]


skills_registry = SkillsRegistry()


def _read_status_handler(payload: dict[str, Any]) -> dict[str, Any]:
    topic = str(payload.get("topic") or "system").strip() or "system"
    return {"ok": True, "message": f"Read-only status for {topic}", "topic": topic}


def _create_task_handler(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "Neue Aufgabe").strip() or "Neue Aufgabe"
    return {"ok": True, "message": "Task scheduled", "title": title}


skills_registry.register_skill(
    "read_status",
    _read_status_handler,
    read_only=True,
    requires_confirm=False,
    audit_event="ai_skill_read_status",
)
skills_registry.register_skill(
    "create_task",
    _create_task_handler,
    read_only=False,
    requires_confirm=True,
    audit_event="ai_skill_create_task",
)


def suggest_skills(prompt: str) -> list[SkillDefinition]:
    text = str(prompt or "").lower()
    if not text:
        return []
    suggested: list[SkillDefinition] = []
    if any(token in text for token in ("create", "schreibe", "ändern", "update", "delete", "send")):
        skill = skills_registry.get("create_task")
        if skill:
            suggested.append(skill)
    if any(token in text for token in ("status", "read", "zeige", "list", "overview")):
        skill = skills_registry.get("read_status")
        if skill:
            suggested.append(skill)
    # deny-by-default on uncertainty: no suggestion if no deterministic mapping hit.
    return suggested
