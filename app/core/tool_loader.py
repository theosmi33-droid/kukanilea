from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass, field
from typing import Any

from app.tools.base_tool import BaseTool
from app.tools.registry import registry

logger = logging.getLogger("kukanilea.core.tool_loader")

REQUIRED_TOOL_ATTRIBUTES = ("name", "description", "input_schema", "run", "endpoints")


@dataclass
class ToolVerificationResult:
    tool_name: str
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class ToolLoaderReport:
    imported_modules: list[str] = field(default_factory=list)
    failed_modules: list[dict[str, str]] = field(default_factory=list)
    loaded_tools: list[str] = field(default_factory=list)
    failed_tools: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed_modules and not self.failed_tools


def verify_tool_interface(tool: BaseTool) -> ToolVerificationResult:
    """Validate that a tool satisfies the Core Tool Interface contract."""
    errors: list[str] = []
    for attr in REQUIRED_TOOL_ATTRIBUTES:
        if not hasattr(tool, attr):
            errors.append(f"missing attribute '{attr}'")

    name = getattr(tool, "name", "")
    if not isinstance(name, str) or not name.strip():
        errors.append("name must be a non-empty string")

    description = getattr(tool, "description", "")
    if not isinstance(description, str) or not description.strip():
        errors.append("description must be a non-empty string")

    input_schema = getattr(tool, "input_schema", None)
    if not isinstance(input_schema, dict):
        errors.append("input_schema must be a dict")

    run_fn = getattr(tool, "run", None)
    if not callable(run_fn):
        errors.append("run must be callable")

    endpoints = getattr(tool, "endpoints", None)
    if not isinstance(endpoints, list) or not endpoints:
        errors.append("endpoints must be a non-empty list")
    else:
        for endpoint in endpoints:
            if not isinstance(endpoint, str) or not endpoint.startswith("/"):
                errors.append("all endpoints must be absolute paths starting with '/'")
                break

    return ToolVerificationResult(tool_name=name or tool.__class__.__name__, valid=not errors, errors=errors)


def _discover_tool_classes(module: Any) -> list[type[BaseTool]]:
    classes: list[type[BaseTool]] = []
    for value in vars(module).values():
        if not isinstance(value, type):
            continue
        if not issubclass(value, BaseTool) or value is BaseTool:
            continue
        classes.append(value)
    return classes


def load_all_tools(app=None) -> dict[str, Any]:
    """Load all tool modules, register discovered tool blueprints, and verify contract compliance."""
    import app.tools as tools_pkg

    report = ToolLoaderReport()

    for _, module_name, _ in pkgutil.iter_modules(tools_pkg.__path__):
        if module_name in {"registry", "base_tool"}:
            continue

        full_name = f"app.tools.{module_name}"
        try:
            module = importlib.import_module(full_name)
            report.imported_modules.append(full_name)
        except Exception as exc:
            logger.error("Failed to load tool module %s: %s", module_name, exc)
            report.failed_modules.append({"module": full_name, "error": str(exc)})
            continue

        for tool_cls in _discover_tool_classes(module):
            tool_name = str(getattr(tool_cls, "name", "") or tool_cls.__name__)
            instance = registry.get(tool_name)
            if instance is None:
                try:
                    instance = tool_cls()
                    registry.register(instance)
                except Exception as exc:
                    report.failed_tools.append({
                        "tool": tool_name,
                        "error": f"failed to instantiate/register: {exc}",
                    })
                    continue

            verification = verify_tool_interface(instance)
            if verification.valid:
                report.loaded_tools.append(verification.tool_name)
            else:
                report.failed_tools.append({
                    "tool": verification.tool_name,
                    "errors": verification.errors,
                })

    payload = {
        "ok": report.ok,
        "imported_modules": sorted(set(report.imported_modules)),
        "failed_modules": report.failed_modules,
        "loaded_tools": sorted(set(report.loaded_tools)),
        "failed_tools": report.failed_tools,
        "required_attributes": list(REQUIRED_TOOL_ATTRIBUTES),
    }

    if app is not None:
        app.config["TOOL_LOADER_REPORT"] = payload
        app.config["TOOL_LOADER_LOADED_TOOLS"] = payload["loaded_tools"]
        app.config["TOOL_LOADER_FAILED_TOOLS"] = payload["failed_tools"]

    logger.info(
        "Tool loader finished: imported=%s loaded=%s failed_modules=%s failed_tools=%s",
        len(payload["imported_modules"]),
        len(payload["loaded_tools"]),
        len(payload["failed_modules"]),
        len(payload["failed_tools"]),
    )

    return payload
