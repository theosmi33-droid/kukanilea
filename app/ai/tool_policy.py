from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchContactsArgs(StrictModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


class SearchDocumentsArgs(StrictModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


class CreateTaskArgs(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    severity: str = Field(default="INFO", min_length=1, max_length=32)
    task_type: str = Field(default="GENERAL", min_length=1, max_length=32)
    details: str = Field(default="", max_length=5000)


TOOL_ARG_MODELS: dict[str, type[BaseModel]] = {
    "search_contacts": SearchContactsArgs,
    "search_documents": SearchDocumentsArgs,
    "create_task": CreateTaskArgs,
}

ALLOWED_TOOLS: set[str] = set(TOOL_ARG_MODELS.keys())
MUTATION_TOOLS: set[str] = {"create_task"}


@dataclass(frozen=True)
class ToolDecision:
    tool_name: str
    args: dict[str, Any]
    requires_confirm: bool


def is_mutation(tool_name: str) -> bool:
    return str(tool_name or "") in MUTATION_TOOLS


def validate_tool_call(tool_name: str, args: dict[str, Any]) -> ToolDecision:
    name = str(tool_name or "").strip()
    if name not in ALLOWED_TOOLS:
        raise ValueError(f"tool_not_allowed:{name}")
    model = TOOL_ARG_MODELS[name]
    try:
        parsed = model.model_validate(args or {})
    except ValidationError as exc:
        err = exc.errors()[0] if exc.errors() else {"msg": "validation_error"}
        raise ValueError(
            f"validation_error:{err.get('msg', 'validation_error')}"
        ) from exc

    return ToolDecision(
        tool_name=name,
        args=parsed.model_dump(),
        requires_confirm=(name in MUTATION_TOOLS),
    )
