# 0014: Entity Links v0

## Status
Accepted

## Entscheidung
- Einführung einer generischen `entity_links` Tabelle.
- Canonical ordering für symmetrische Duplikatvermeidung.
- Keine Anzeige/Logik auf Basis potenziell PII-haltiger Entitätstitel.
- Eventlog-Payloads bleiben PII-frei.

## Begründung
- Minimale Kopplung zwischen Modulen (Leads/CRM/Knowledge).
- Stabiler Link-Layer als Grundlage für weitere Quellen und Konvertierungen.
- Security-first bei gleichzeitiger Bedienbarkeit (manuelle Link-UI).

## v0 Limits
- Keine automatische Link-Erkennung.
- Optionaler Existence-Check nur für bekannte Typen/Tabellen.
- Kein Bulk-Linking.
