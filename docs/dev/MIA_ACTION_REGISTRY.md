# MIA Action Registry (metadatengetrieben)

Die MIA-Action-Registry erzeugt adressierbare Handlungen deklarativ aus einer Taxonomie statt aus einzeln programmierten Spezialfunktionen.

## Kernmodell

`ActionSpec` in `app/tools/action_registry.py` ist das kanonische Laufzeitmodell mit:

- `action_id`
- `domain`
- `entity`
- `verb`
- `modifier`
- `description`
- `params_schema`
- `output_schema`
- `requires_confirm`
- `risk_level`
- `audit_event_type`
- `idempotency_key_strategy`
- `enabled`
- `tags`
- plus Tool-Verknüpfung (`tool_name`, `source_action_name`) und Policy-Hilfsfelder (`permissions`, `audit_fields`, `is_critical`).

## Registrierungslogik

1. Tools registrieren sich weiterhin zentral über `app/tools/registry.py`.
2. Bei `register_tool(tool)` liest die Action-Registry die deklarativen Tool-Actions (`tool.actions()`).
3. Für jedes Tool wird eine Domäne aufgelöst (`_resolve_domain`).
4. Die Registry kombiniert deterministisch:
   - Domänen-Entitäten (`DOMAIN_ENTITIES`)
   - Kernverben (`CORE_VERBS`)
   - Modifier (`MODIFIERS`)
5. Daraus wird pro Kombination ein vollständiges `ActionSpec` mit Confirm-, Risk-, Audit- und Idempotency-Metadaten erzeugt.

## Erweiterung für neue Tools

Neues Tool hinzufügen:

- Tool in `app/tools/` anlegen (von `BaseTool` ableiten).
- Tool per `registry.register(...)` registrieren.
- Optional: Domäne in `DOMAIN_ENTITIES` ergänzen oder Mapping in `_resolve_domain` erweitern.
- Tool-spezifische Param-Schemas/Permissions/Audit-Felder über `actions()` deklarativ liefern.

Damit skaliert MIA über neue Taxonomieeinträge, ohne einzelne Aktion-Funktionen manuell zu vervielfachen.
