# RBAC (Rollen und Berechtigungen)

Stand: 2026-02-20

KUKANILEA erzwingt Autorisierung serverseitig nach dem Prinzip `deny-by-default`.

## Systemrollen

- `OWNER_ADMIN`: Kunden-Admin, darf Einstellungen/Berechtigungen und Benutzerrollen verwalten.
- `BAULEITUNG`: Operative Rolle mit Schreibrechten in Kernmodulen.
- `OFFICE`: Buerorolle mit CRM/Tasks/Dokument-Rechten.
- `SUPPORT`: Eingeschraenkte Rolle mit primar lesenden Rechten.
- `DEV`: Technische Rolle fuer DEV-Routen (Update Center, Tenant-Metadaten, Tools).

## Permission-Manager

- UI: `/settings/permissions`
- Zugriff: nur Benutzer mit `settings.manage_permissions`
- Rollenrechte pflegen: Owner Admin + DEV
- `DEV`-Rollenrechte duerfen nur durch `DEV` veraendert werden

## Owner-Admin Guard

- Genau ein `OWNER_ADMIN` pro Installation.
- Beim Zuweisen wird serverseitig validiert:
  - mindestens ein `OWNER_ADMIN` muss existieren
  - mehr als ein `OWNER_ADMIN` ist unzulaessig

## Legacy-Migration

- Legacy-Rollen werden automatisch gemappt:
  - `ADMIN -> OWNER_ADMIN`
  - `OPERATOR -> OFFICE`
  - `READONLY -> SUPPORT`
  - `DEV -> DEV`
- Bestehende Memberships bleiben erhalten; RBAC-Rollen werden idempotent ergänzt.
