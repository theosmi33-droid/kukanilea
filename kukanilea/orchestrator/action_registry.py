from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any, Iterable, Mapping

WRITE_VERBS = {
    "create",
    "update",
    "delete",
    "reply",
    "send",
    "assign",
    "approve",
    "schedule",
    "sync",
    "restore",
}


@dataclass(frozen=True)
class RiskPolicy:
    name: str
    level: str
    description: str


@dataclass(frozen=True)
class ActionPolicyMetadata:
    confirm_required: bool
    audit_required: bool
    risk: str
    external_call: bool
    idempotency: str


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    domain: str
    entity: str
    verb: str
    modifiers: tuple[str, ...]
    tool: str
    parameter_schema: dict[str, Any]
    policy: ActionPolicyMetadata

    @property
    def action(self) -> str:
        return self.action_id

    @property
    def is_write(self) -> bool:
        return self.verb in WRITE_VERBS


@dataclass(frozen=True)
class EntitySpec:
    name: str
    verbs: tuple[str, ...]
    parameter_schema: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParameterValidationResult:
    ok: bool
    missing_required: tuple[str, ...] = ()
    unknown_parameters: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainSpec:
    name: str
    tool: str
    entities: tuple[EntitySpec, ...]
    modifiers: tuple[str, ...] = ()
    external_verbs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionRegistryStats:
    registered_actions: int
    derivable_action_ids: int
    domain_count: int


@dataclass
class ActionRegistry:
    actions: dict[str, ActionSpec] = field(default_factory=dict)
    domains: dict[str, DomainSpec] = field(default_factory=dict)

    def register(self, action_spec: ActionSpec) -> None:
        if action_spec.action_id in self.actions:
            raise ValueError(f"Duplicate action id: {action_spec.action_id}")
        self.actions[action_spec.action_id] = action_spec

    def bulk_register(self, action_specs: Iterable[ActionSpec]) -> None:
        for spec in action_specs:
            self.register(spec)

    def get(self, action_id: str) -> ActionSpec | None:
        return self.actions.get(action_id)

    def as_dict(self) -> dict[str, ActionSpec]:
        return dict(self.actions)

    def validate(self) -> None:
        for action_id, spec in self.actions.items():
            policy = spec.policy
            if policy is None:
                raise ValueError(f"Missing policy metadata: {action_id}")
            required_values = [policy.risk, policy.idempotency]
            if any(not str(v).strip() for v in required_values):
                raise ValueError(f"Incomplete policy metadata: {action_id}")
            if spec.is_write and (not policy.confirm_required or not policy.audit_required):
                raise ValueError(f"Write action without confirm+audit policy: {action_id}")
            _validate_parameter_schema(spec.parameter_schema, action_id=action_id)

    def validate_action_params(self, action_id: str, params: Mapping[str, Any] | None) -> ParameterValidationResult:
        spec = self.get(action_id)
        if spec is None:
            return ParameterValidationResult(ok=False)
        schema = normalize_parameter_schema(spec.parameter_schema)
        properties = schema.get("properties") or {}
        allowed = set(str(key) for key in properties.keys())
        required = set(str(item) for item in (schema.get("required") or []))
        provided = dict(params or {})
        provided_keys = set(str(key) for key in provided.keys())
        unknown = tuple(sorted(provided_keys - allowed))
        missing = tuple(sorted(key for key in required if key not in provided_keys))
        return ParameterValidationResult(
            ok=not unknown and not missing,
            missing_required=missing,
            unknown_parameters=unknown,
        )

    def stats(self) -> ActionRegistryStats:
        derivable = sum(_count_derivable_actions(spec) for spec in self.domains.values())
        return ActionRegistryStats(
            registered_actions=len(self.actions),
            derivable_action_ids=derivable,
            domain_count=len(self.domains),
        )


def canonical_action_id(domain: str, entity: str, verb: str, modifiers: Iterable[str] = ()) -> str:
    segments = [domain, entity, verb, *[m for m in modifiers if m]]
    return ".".join(segment.strip().lower().replace(" ", "_") for segment in segments if segment)


def compose_modifiers(modifiers: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    if not modifiers:
        return ((),)
    combinations: list[tuple[str, ...]] = [()]
    for size in range(1, len(modifiers) + 1):
        for combo in product((False, True), repeat=len(modifiers)):
            if sum(combo) != size:
                continue
            picked = tuple(modifiers[idx] for idx, enabled in enumerate(combo) if enabled)
            combinations.append(picked)
    unique: list[tuple[str, ...]] = []
    for combo in combinations:
        if combo not in unique:
            unique.append(combo)
    return tuple(unique)


def generate_domain_actions(
    domain_spec: DomainSpec,
    *,
    risk_policies: Mapping[str, RiskPolicy],
) -> list[ActionSpec]:
    actions: list[ActionSpec] = []
    modifier_sets = compose_modifiers(domain_spec.modifiers)
    for entity in domain_spec.entities:
        schema = normalize_parameter_schema(entity.parameter_schema)
        for verb in entity.verbs:
            for modifiers in modifier_sets:
                action_id = canonical_action_id(domain_spec.name, entity.name, verb, modifiers)
                is_write = verb in WRITE_VERBS
                risk_key = "high" if verb in domain_spec.external_verbs else ("medium" if is_write else "low")
                policy = ActionPolicyMetadata(
                    confirm_required=is_write,
                    audit_required=True,
                    risk=risk_policies[risk_key].name,
                    external_call=verb in domain_spec.external_verbs,
                    idempotency="idempotent" if verb in {"read", "list", "status", "lookup", "search"} else "non_idempotent",
                )
                actions.append(
                    ActionSpec(
                        action_id=action_id,
                        domain=domain_spec.name,
                        entity=entity.name,
                        verb=verb,
                        modifiers=modifiers,
                        tool=domain_spec.tool,
                        parameter_schema=schema,
                        policy=policy,
                    )
                )
    return actions


def _count_derivable_actions(domain_spec: DomainSpec) -> int:
    variants = len(compose_modifiers(domain_spec.modifiers))
    return sum(len(entity.verbs) * variants for entity in domain_spec.entities)


def normalize_parameter_schema(schema: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(schema or {})
    if raw.get("type") == "object" and isinstance(raw.get("properties"), Mapping):
        normalized = {
            "type": "object",
            "properties": dict(raw.get("properties") or {}),
            "required": list(raw.get("required") or []),
            "additionalProperties": bool(raw.get("additionalProperties", False)),
        }
        return normalized

    properties: dict[str, dict[str, str]] = {}
    required: list[str] = []
    for key, value in raw.items():
        param_type = _to_json_schema_type(value)
        properties[str(key)] = {"type": param_type}
        if str(key) in {"tenant", "query", "payload"}:
            required.append(str(key))

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _to_json_schema_type(value: Any) -> str:
    text = str(value or "string").strip().lower()
    aliases = {
        "str": "string",
        "string": "string",
        "int": "integer",
        "integer": "integer",
        "float": "number",
        "number": "number",
        "bool": "boolean",
        "boolean": "boolean",
        "dict": "object",
        "object": "object",
        "list": "array",
        "array": "array",
    }
    return aliases.get(text, "string")


def _validate_parameter_schema(schema: Mapping[str, Any], *, action_id: str) -> None:
    if schema.get("type") != "object":
        raise ValueError(f"Invalid parameter schema type for action: {action_id}")
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        raise ValueError(f"Invalid parameter schema properties for action: {action_id}")
    required = schema.get("required") or []
    if not isinstance(required, list):
        raise ValueError(f"Invalid parameter schema required list for action: {action_id}")
    unknown_required = [key for key in required if key not in properties]
    if unknown_required:
        raise ValueError(f"Required parameters must be declared in properties for action: {action_id}")
