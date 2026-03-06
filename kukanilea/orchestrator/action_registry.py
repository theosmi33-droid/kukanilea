from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Iterable, Mapping

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
    parameter_schema: dict[str, str]
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
    parameter_schema: Mapping[str, str] = field(default_factory=dict)


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
        schema = dict(entity.parameter_schema)
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
