from __future__ import annotations

from .action_registry import (
    ActionRegistry,
    DomainSpec,
    EntitySpec,
    RiskPolicy,
    detect_duplicate_action_ids,
    generate_domain_actions,
)

RISK_POLICIES: dict[str, RiskPolicy] = {
    "low": RiskPolicy("low", "low", "Read-only/local lookup action."),
    "medium": RiskPolicy("medium", "medium", "State-changing action requiring confirmation."),
    "high": RiskPolicy("high", "high", "External or high-impact action requiring strict controls."),
}

COMMON_VERBS = ("read", "list", "search", "create", "update", "delete", "status")
SCHEDULING_VERBS = ("read", "list", "search", "create", "update", "delete", "schedule")
COMMUNICATION_VERBS = ("read", "list", "search", "reply", "send", "status")

LEGACY_ACTION_ALIASES: dict[str, str] = {
    "dashboard.read": "dashboard.summary.read",
    "crm.search_customer": "crm.customer.search",
    "task.create": "tasks.task.create",
    "calendar.create_appointment": "calendar.appointment.create",
    "dms.search_invoice": "dms.invoice.search",
    "warehouse.material_check": "warehouse.material.status",
    "messenger.reply": "messenger.message.reply",
}


def _make_entities(*names: str, verbs: tuple[str, ...] = COMMON_VERBS, schema: dict[str, str] | None = None) -> tuple[EntitySpec, ...]:
    payload = schema or {"tenant": "str", "query": "str", "payload": "dict"}
    return tuple(EntitySpec(name=name, verbs=verbs, parameter_schema=payload) for name in names)


def domain_specs() -> tuple[DomainSpec, ...]:
    return (
        DomainSpec("dashboard", "dashboard", _make_entities("summary", "kpi", "timeline", "alerts", verbs=("read", "list", "status")), modifiers=("cached", "projected", "tenant_scoped")),
        DomainSpec("crm", "crm", _make_entities("customer", "lead", "contact", "account", "opportunity", verbs=COMMON_VERBS), modifiers=("tenant_scoped", "strict")),
        DomainSpec("tasks", "tasks", _make_entities("task", "checklist", "work_item", "reminder", verbs=SCHEDULING_VERBS), modifiers=("tenant_scoped", "priority", "sla")),
        DomainSpec("calendar", "calendar", _make_entities("appointment", "availability", "shift", "resource", verbs=SCHEDULING_VERBS), modifiers=("tenant_scoped", "timezone", "conflict_checked")),
        DomainSpec("dms", "dms", _make_entities("invoice", "offer", "delivery_note", "document", "contract", verbs=COMMON_VERBS), modifiers=("tenant_scoped", "compliance", "archive")),
        DomainSpec("warehouse", "warehouse", _make_entities("material", "stock", "order", "supplier", "reservation", verbs=COMMON_VERBS), modifiers=("tenant_scoped", "realtime", "critical")),
        DomainSpec("messenger", "messenger", _make_entities("message", "thread", "channel", "template", verbs=COMMUNICATION_VERBS), modifiers=("tenant_scoped", "encrypted", "tracked"), external_verbs=("reply", "send")),
        DomainSpec("mail", "mail", _make_entities("mail", "draft", "inbox", "outbox", verbs=COMMUNICATION_VERBS), modifiers=("tenant_scoped", "encrypted", "audit"), external_verbs=("reply", "send")),
        DomainSpec("files", "filesystem", _make_entities("file", "folder", "bundle", "export", verbs=COMMON_VERBS), modifiers=("tenant_scoped", "versioned", "signed")),
        DomainSpec("security", "sec", _make_entities("scan", "policy", "incident", "access", verbs=("read", "list", "search", "create", "update", "status", "approve")), modifiers=("tenant_scoped", "strict", "forensics")),
        DomainSpec("network", "network", _make_entities("peer", "sync", "endpoint", "route", verbs=("read", "list", "search", "create", "update", "status", "sync")), modifiers=("tenant_scoped", "secure", "mesh"), external_verbs=("sync",)),
        DomainSpec("ai", "ai", _make_entities("prompt", "memory", "analysis", "classification", verbs=("read", "list", "search", "create", "update", "status")), modifiers=("tenant_scoped", "reviewed", "grounded")),
    )


def create_action_registry() -> ActionRegistry:
    registry = ActionRegistry()
    for domain in domain_specs():
        registry.domains[domain.name] = domain
        generated_actions = generate_domain_actions(domain, risk_policies=RISK_POLICIES)
        duplicates = detect_duplicate_action_ids(generated_actions)
        if duplicates:
            raise ValueError(f"Duplicate generated action ids in domain '{domain.name}': {', '.join(duplicates)}")
        registry.bulk_register(generated_actions)

    # Compatibility aliases for existing deterministic router intents.
    alias_ids = (
        "dashboard.summary.read",
        "crm.customer.search",
        "tasks.task.create",
        "calendar.appointment.create",
        "dms.invoice.search",
        "warehouse.material.status",
        "messenger.message.reply",
    )
    for alias in alias_ids:
        if alias not in registry.actions:
            raise ValueError(f"Expected canonical action missing from generated registry: {alias}")

    for legacy_action, canonical_action in LEGACY_ACTION_ALIASES.items():
        registry.register_legacy_alias(legacy_action, canonical_action)

    registry.validate()
    return registry


def registry_summary() -> dict[str, int]:
    registry = create_action_registry()
    stats = registry.stats()
    return {
        "registered_actions": stats.registered_actions,
        "derivable_actions": stats.derivable_action_ids,
        "domains": stats.domain_count,
        "write_actions": stats.write_actions,
        "external_actions": stats.external_actions,
    }


def derived_registry_artifact() -> dict[str, object]:
    """Generate a derived snapshot for reporting/export without becoming a second source of truth."""
    registry = create_action_registry()
    validation = registry.validation_summary()
    return {
        "summary": registry_summary(),
        "validation": {
            "valid": validation.is_valid,
            "duplicate_action_ids": list(validation.duplicate_action_ids),
            "incomplete_policy_action_ids": list(validation.incomplete_policy_action_ids),
            "non_derivable_action_ids": list(validation.non_derivable_action_ids),
        },
    }
