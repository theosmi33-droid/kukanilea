from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import product
from typing import Iterable, Mapping
import warnings

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
    write_actions: int
    external_actions: int


@dataclass(frozen=True)
class ActionRegistryValidationSummary:
    duplicate_action_ids: tuple[str, ...]
    incomplete_policy_action_ids: tuple[str, ...]
    non_derivable_action_ids: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.duplicate_action_ids and not self.incomplete_policy_action_ids and not self.non_derivable_action_ids


@dataclass
class ActionRegistry:
    actions: dict[str, ActionSpec] = field(default_factory=dict)
    domains: dict[str, DomainSpec] = field(default_factory=dict)
    legacy_aliases: dict[str, str] = field(default_factory=dict)

    def register(self, action_spec: ActionSpec) -> None:
        if action_spec.action_id in self.actions:
            raise ValueError(f"Duplicate action id: {action_spec.action_id}")
        self.actions[action_spec.action_id] = action_spec

    def bulk_register(self, action_specs: Iterable[ActionSpec]) -> None:
        for spec in action_specs:
            self.register(spec)

    def register_legacy_alias(self, legacy_action_id: str, canonical_action_id: str) -> None:
        legacy = str(legacy_action_id or "").strip()
        canonical = str(canonical_action_id or "").strip()
        if not legacy or not canonical:
            raise ValueError("Alias mapping requires legacy and canonical action ids")
        self.legacy_aliases[legacy] = canonical

    def resolve_action_id(self, action_id: str) -> str | None:
        action = str(action_id or "").strip()
        if action in self.actions:
            return action
        canonical = self.legacy_aliases.get(action)
        if canonical and canonical in self.actions:
            warnings.warn(
                f"Action '{action}' is deprecated and will be removed; use '{canonical}'.",
                DeprecationWarning,
                stacklevel=2,
            )
            return canonical
        return None

    def get(self, action_id: str) -> ActionSpec | None:
        resolved = self.resolve_action_id(action_id)
        if not resolved:
            return None
        return self.actions.get(resolved)

    def as_dict(self) -> dict[str, ActionSpec]:
        return dict(self.actions)

    def derivable_action_ids(self) -> set[str]:
        derivable: set[str] = set()
        for domain in self.domains.values():
            for entity in domain.entities:
                for verb in entity.verbs:
                    for modifiers in compose_modifiers(domain.modifiers):
                        derivable.add(canonical_action_id(domain.name, entity.name, verb, modifiers))
        return derivable

    def validation_summary(self) -> ActionRegistryValidationSummary:
        policy_issues: list[str] = []
        for action_id, spec in self.actions.items():
            policy = spec.policy
            if policy is None:
                policy_issues.append(action_id)
                continue
            required_values = [policy.risk, policy.idempotency]
            if any(not str(v).strip() for v in required_values):
                policy_issues.append(action_id)

        derivable_action_ids = self.derivable_action_ids()
        non_derivable = sorted(action_id for action_id in self.actions if action_id not in derivable_action_ids)
        return ActionRegistryValidationSummary(
            duplicate_action_ids=(),
            incomplete_policy_action_ids=tuple(sorted(policy_issues)),
            non_derivable_action_ids=tuple(non_derivable),
        )

    def validate(self) -> None:
        summary = self.validation_summary()
        if summary.duplicate_action_ids:
            raise ValueError(f"Duplicate action ids found: {', '.join(summary.duplicate_action_ids)}")
        if summary.incomplete_policy_action_ids:
            raise ValueError(
                f"Incomplete policy metadata: {', '.join(summary.incomplete_policy_action_ids)}"
            )
        for action_id, spec in self.actions.items():
            policy = spec.policy
            expected_action_id = canonical_action_id(spec.domain, spec.entity, spec.verb, spec.modifiers)
            if action_id != expected_action_id:
                raise ValueError(f"Non-canonical action id: {action_id} != {expected_action_id}")
            if not isinstance(spec.parameter_schema, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in spec.parameter_schema.items()
            ):
                raise ValueError(f"Invalid parameter schema metadata: {action_id}")
            if spec.is_write and (not policy.confirm_required or not policy.audit_required):
                raise ValueError(f"Write action without confirm+audit policy: {action_id}")
            if spec.is_write and policy.idempotency == "idempotent":
                raise ValueError(f"Write action marked idempotent: {action_id}")
            if policy.external_call:
                if policy.risk != "high":
                    raise ValueError(f"External action without high risk policy: {action_id}")
                if not policy.confirm_required or not policy.audit_required:
                    raise ValueError(f"External action without confirm+audit policy: {action_id}")

        if self.domains and summary.non_derivable_action_ids:
            raise ValueError(
                f"Non-derivable registered action ids: {', '.join(summary.non_derivable_action_ids)}"
            )

    def stats(self) -> ActionRegistryStats:
        derivable = sum(_count_derivable_actions(spec) for spec in self.domains.values())
        return ActionRegistryStats(
            registered_actions=len(self.actions),
            derivable_action_ids=derivable,
            domain_count=len(self.domains),
            write_actions=sum(1 for spec in self.actions.values() if spec.is_write),
            external_actions=sum(1 for spec in self.actions.values() if spec.policy.external_call),
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


def detect_duplicate_action_ids(action_specs: Iterable[ActionSpec]) -> tuple[str, ...]:
    counter = Counter(spec.action_id for spec in action_specs)
    return tuple(sorted(action_id for action_id, count in counter.items() if count > 1))


def _count_derivable_actions(domain_spec: DomainSpec) -> int:
    variants = len(compose_modifiers(domain_spec.modifiers))
    return sum(len(entity.verbs) * variants for entity in domain_spec.entities)
