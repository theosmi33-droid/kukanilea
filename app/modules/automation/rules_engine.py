from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

SUPPORTED_TRIGGERS = {
    "new_lead",
    "new_upload",
    "overdue_invoice",
    "unanswered_message",
}
SUPPORTED_ACTIONS = {
    "create_task",
    "notify",
    "create_draft",
    "schedule_follow_up",
}


class ActionExecutor(Protocol):
    def __call__(self, action_type: str, payload: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]: ...


def _parse_scalar(value: str) -> Any:
    raw = value.strip()
    if raw in {"", "null", "~"}:
        return None
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        return raw


def _parse_simple_yaml(text: str) -> Any:
    lines = [line.rstrip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        raise ValueError("validation_error")

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    for line in lines:
        indent = len(line) - len(line.lstrip(" "))
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        stripped = line.strip()

        if stripped.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError("validation_error")
            item_text = stripped[2:].strip()
            if ":" in item_text:
                key, _, val = item_text.partition(":")
                item: dict[str, Any] = {key.strip(): _parse_scalar(val)}
                parent.append(item)
                stack.append((indent, item))
            else:
                parent.append(_parse_scalar(item_text))
            continue

        key, sep, val = stripped.partition(":")
        if not sep or not isinstance(parent, dict):
            raise ValueError("validation_error")
        k = key.strip()
        v = val.strip()

        if v == "":
            next_obj: Any = [] if k == "actions" or k == "rules" else {}
            parent[k] = next_obj
            stack.append((indent, next_obj))
        else:
            parent[k] = _parse_scalar(v)

    return root



@dataclass
class RuleExecutionLog:
    rule_id: str
    trigger: str
    action: str
    status: str
    attempts: int
    idempotency_key: str
    error: str = ""
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


@dataclass
class RulesEngineState:
    processed_keys: set[str] = field(default_factory=set)
    logs: list[RuleExecutionLog] = field(default_factory=list)


class RulesEngine:
    def __init__(self, rules: list[dict[str, Any]]):
        self.rules = [self._normalize_rule(rule) for rule in rules]

    @classmethod
    def from_config_text(cls, text: str) -> "RulesEngine":
        raw = cls._parse_config_text(text)
        if isinstance(raw, dict):
            raw_rules = raw.get("rules")
        else:
            raw_rules = raw
        if not isinstance(raw_rules, list):
            raise ValueError("validation_error")
        return cls(raw_rules)

    @staticmethod
    def _parse_config_text(text: str) -> Any:
        text = str(text or "").strip()
        if not text:
            raise ValueError("validation_error")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return _parse_simple_yaml(text)

    def _normalize_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(rule, dict):
            raise ValueError("validation_error")
        rid = str(rule.get("id") or "").strip()
        trigger = str(rule.get("trigger") or "").strip().lower()
        actions = rule.get("actions")
        if not rid or trigger not in SUPPORTED_TRIGGERS or not isinstance(actions, list) or not actions:
            raise ValueError("validation_error")
        norm_actions: list[dict[str, Any]] = []
        for action in actions:
            if not isinstance(action, dict):
                raise ValueError("validation_error")
            action_type = str(action.get("type") or "").strip().lower()
            if action_type not in SUPPORTED_ACTIONS:
                raise ValueError("validation_error")
            payload = action.get("payload")
            norm_actions.append({"type": action_type, "payload": payload if isinstance(payload, dict) else {}})
        retry = rule.get("retry") if isinstance(rule.get("retry"), dict) else {}
        max_attempts = max(1, min(int(retry.get("max_attempts", 3) or 3), 10))
        return {
            "id": rid,
            "trigger": trigger,
            "actions": norm_actions,
            "retry": {"max_attempts": max_attempts},
        }

    def process_event(
        self,
        event: dict[str, Any],
        *,
        executor: ActionExecutor,
        state: RulesEngineState | None = None,
    ) -> dict[str, Any]:
        st = state or RulesEngineState()
        event_id = str(event.get("id") or event.get("event_id") or "").strip()
        trigger = str(event.get("trigger") or "").strip().lower()
        if not event_id or trigger not in SUPPORTED_TRIGGERS:
            raise ValueError("validation_error")

        executed = 0
        skipped = 0
        failed = 0
        for rule in self.rules:
            if rule["trigger"] != trigger:
                continue
            for index, action in enumerate(rule["actions"]):
                idempotency_key = f"{rule['id']}:{event_id}:{index}:{action['type']}"
                if idempotency_key in st.processed_keys:
                    skipped += 1
                    st.logs.append(
                        RuleExecutionLog(
                            rule_id=rule["id"],
                            trigger=trigger,
                            action=action["type"],
                            status="skipped",
                            attempts=0,
                            idempotency_key=idempotency_key,
                            error="duplicate",
                        )
                    )
                    continue

                max_attempts = int(rule["retry"]["max_attempts"])
                last_error = ""
                for attempt in range(1, max_attempts + 1):
                    try:
                        result = executor(action["type"], action["payload"], event)
                        if not isinstance(result, dict) or result.get("ok", True) is False:
                            raise RuntimeError(str(result.get("error") or "execution_failed"))
                        st.processed_keys.add(idempotency_key)
                        executed += 1
                        st.logs.append(
                            RuleExecutionLog(
                                rule_id=rule["id"],
                                trigger=trigger,
                                action=action["type"],
                                status="ok",
                                attempts=attempt,
                                idempotency_key=idempotency_key,
                            )
                        )
                        break
                    except Exception as exc:
                        last_error = str(exc)
                        if attempt >= max_attempts:
                            failed += 1
                            st.logs.append(
                                RuleExecutionLog(
                                    rule_id=rule["id"],
                                    trigger=trigger,
                                    action=action["type"],
                                    status="failed",
                                    attempts=attempt,
                                    idempotency_key=idempotency_key,
                                    error=last_error,
                                )
                            )

        return {
            "ok": failed == 0,
            "executed": executed,
            "skipped": skipped,
            "failed": failed,
            "logs": [log.__dict__.copy() for log in st.logs],
        }
