from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

ALLOWLIST_OPERATORS = {
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "present",
}


def canonicalize_condition_config(config: Any) -> str:
    return json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _evaluate_leaf(
    *,
    condition: Mapping[str, Any],
    context: Mapping[str, Any],
    allowed_fields: set[str],
) -> bool:
    field = str(condition.get("field") or "").strip()
    if not field or field not in allowed_fields:
        return False
    value = context.get(field)

    if "present" in condition:
        expected = bool(condition.get("present"))
        return _has_value(value) if expected else not _has_value(value)

    operators = [
        key for key in ALLOWLIST_OPERATORS if key in condition and key != "present"
    ]
    if len(operators) != 1:
        return False
    op = operators[0]
    needle = condition.get(op)
    hay = _as_text(value)
    needle_text = _as_text(needle)

    if op == "equals":
        return hay == needle_text
    if op == "not_equals":
        return hay != needle_text
    if op == "contains":
        return needle_text in hay
    if op == "not_contains":
        return needle_text not in hay
    if op == "starts_with":
        return hay.startswith(needle_text)
    if op == "ends_with":
        return hay.endswith(needle_text)
    return False


def evaluate_conditions(
    condition_config: Any,
    context: Mapping[str, Any],
    *,
    allowed_fields: Sequence[str] | None = None,
) -> bool:
    if not isinstance(condition_config, Mapping):
        return False
    if not isinstance(context, Mapping):
        return False

    fields = {
        str(v).strip() for v in (allowed_fields or context.keys()) if str(v).strip()
    }
    if not fields:
        return False

    if "all" in condition_config:
        items = condition_config.get("all")
        if not isinstance(items, list) or not items:
            return False
        return all(
            evaluate_conditions(item, context, allowed_fields=fields)
            for item in items
            if isinstance(item, Mapping)
        ) and all(isinstance(item, Mapping) for item in items)

    if "any" in condition_config:
        items = condition_config.get("any")
        if not isinstance(items, list) or not items:
            return False
        typed = [item for item in items if isinstance(item, Mapping)]
        if len(typed) != len(items):
            return False
        return any(
            evaluate_conditions(item, context, allowed_fields=fields) for item in typed
        )

    return _evaluate_leaf(
        condition=condition_config, context=context, allowed_fields=fields
    )
