# KUKANILEA MIA Action Registry Architecture

## Zielbild
Die Registry ist jetzt vom Router entkoppelt und nutzt ein deklaratives Modell mit kanonischen Action-IDs nach Schema:

`domain.entity.verb[.modifier...]`

Beispiel: `messenger.message.reply.encrypted.tracked`

## Bausteine
- `ActionSpec`: Kanonisches Modell für adressierbare Handlungen.
- `ActionPolicyMetadata`: Confirm-, Audit-, Risk-, External-Call- und Idempotency-Metadaten.
- `DomainSpec` + `EntitySpec`: Deklarative Definition von Domains/Entities/Verbs/Modifiern.
- `RiskPolicy`: Einheitliche Risiko-Klassen (`low`, `medium`, `high`).
- `ActionRegistry`: Registrierung, Validierung und Statistik.

## Generator-/Loader-Mechanik
`create_action_registry()` lädt deklarative `DomainSpec`-Blöcke und generiert Action-Spezifikationen per kartesischem Produkt über:

- Entities
- Verbs
- Modifier-Kombinationen

Dadurch entstehen aus wenigen Konfigurationszeilen >2000 systematisch adressierbare Action-IDs.

## Validierungsregeln
`ActionRegistry.validate()` erzwingt:
1. keine Duplikate
2. vollständige Policy-Metadaten
3. jede Write-Action benötigt `confirm_required=True` und `audit_required=True`

## Integration in den Manager-Agenten
Der `DeterministicToolRouter` konsumiert die Registry jetzt über `self.action_registry` statt über hardcoded `ACTION_REGISTRY`.
Intent-Mappings zeigen auf kanonische IDs wie `tasks.task.create` oder `dashboard.summary.read`.
