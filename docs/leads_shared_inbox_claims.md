# Leads Shared Inbox Claims v1

## Überblick

Die Shared-Inbox-Mechanik ergänzt Leads um exklusives `Claim`/`Release` mit TTL.

- `Claim`: ein User reserviert die Bearbeitung eines Leads.
- `Release`: nur der Claim-Owner kann freigeben.
- `Auto-Expire`: abgelaufene Claims werden explizit freigegeben.
- `Force Claim`: übersteuert aktiven Fremd-Claim, auditierbar.

## Regeln

- Tenant-sicher: alle Claim-Reads/Writes sind `tenant_id`-gebunden.
- READ_ONLY: alle mutierenden Claim-Endpunkte liefern `403 read_only`.
- Collision-Guard: mutierende Lead-Aktionen laufen zentral über den Guard-Decorator und blocken bei aktivem Fremd-Claim (`403 lead_claimed`).

## Endpunkte

- `POST /leads/<id>/claim`
- `POST /leads/<id>/claim/force`
- `POST /leads/<id>/release`
- `POST /leads/claims/expire-now`

JSON API:

- `POST /api/leads/<id>/claim`
- `POST /api/leads/<id>/release`
- `POST /api/leads/claims/expire-now`

## Eventlog

Claim-Mutationen schreiben Events:

- `lead_claimed`
- `lead_claim_released`
- `lead_claim_expired`
- `lead_claim_reclaimed`

Payloads bleiben PII-frei (nur IDs/User/Zeiten/Reason-Codes).
