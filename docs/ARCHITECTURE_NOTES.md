# Architecture Notes

## Framework discipline (Frappe/ERPNext-inspired principles)

KUKANILEA bleibt Single-Tenant pro Installation, folgt aber klaren Architekturgrenzen:

- Install/Ops-Konfiguration getrennt von Runtime-Session-State.
- Tenant-Kontext wird serverseitig erzwungen (keine vertrauenswuerdigen Client-Tenant-Parameter).
- Security-Policies zentral im App-Entrypoint (`create_app`) statt ad-hoc in einzelnen Routen.
- Externe Runtime-Abhaengigkeiten vermeiden (Offline-/On-Prem-taugliche Auslieferung).

## Operational security defaults

- CSP ist zentral gesetzt und gilt fuer alle Responses.
- Fonts werden nur lokal ausgeliefert (`font-src 'self'`).
- Session-Schutz (Idle + Absolute Timeout) wird serverseitig erzwungen.

## Evolution path

Fuer weitere Framework-Haertung sollten neue Features bevorzugt ueber klar getrennte Subsysteme erfolgen:

- background/queue workers
- migrations/schema governance
- asset pipeline mit reproduzierbaren Builds
- erweiterbare extension points statt route-lokaler Sonderlogik

## RBAC pattern reference (Frappe/ERPNext-inspiriert)

- KUKANILEA nutzt ein Role->Permission-Modell mit serverseitiger Erzwingung pro Request.
- Das orientiert sich konzeptionell an matrixbasierten Berechtigungen (Role/Permission + User-Zuweisung), ohne fremden Code zu uebernehmen.
- Lizenzhinweis: ERPNext steht unter GPL-3.0; daher keine direkte Code-Übernahme in proprietaeren Kundenkontexten.
