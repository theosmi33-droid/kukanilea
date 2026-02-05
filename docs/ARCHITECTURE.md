# KUKANILEA Agent Orchestra Architecture

## Überblick
KUKANILEA nutzt eine Agent-Orchester-Architektur: jede „Tool“-Funktion ist ein eigener Agent. Der Orchestrator analysiert Benutzer-Intent, prüft Berechtigungen (PolicyEngine) und delegiert die Aufgabe an spezialisierte Agenten. Das System ist mandantenfähig (tenant_id), auditierbar und erweiterbar.

## App-Struktur
- `app/__init__.py`: App-Factory (`create_app`) + Blueprint-Registrierung.
- `app/auth.py`: Login, Rollenprüfung, Tenant-Resolution.
- `app/db.py`: User/Tenant/Membership DB für Auth.
- `app/web.py`: UI + API-Routen (Blueprint).

## Kernmodule

### Orchestrator
- **IntentParser**: Regelbasierte Intent-Erkennung + MockLLM-Fallback (deterministisch).
- **Orchestrator**: Validiert Rollen (READONLY, STAFF, ADMIN, DEVELOPER), ruft passende Agenten, sammelt Aktionen für die UI.
- **PolicyEngine**: zentrale RBAC-Prüfung.
- **ToolRegistry**: Auflistung der verfügbaren Tools pro Agent.
- **AgentContext**: tenant_id, user, role, kdnr, token, meta.

### Agenten (kukanilea/agents)
| Agent | Verantwortung | Beispiel | Rolle |
|---|---|---|---|
| UploadAgent | Upload-Queue Hinweise | „Upload starten“ | STAFF |
| ReviewAgent | Review-Flow Hinweise | „Review öffnen“ | STAFF |
| ArchiveAgent | Archiv-Flow Hinweise | „Archivieren“ | STAFF |
| IndexAgent | Indexierung auslösen | „Index neu bauen“ | ADMIN |
| SearchAgent | Strukturierte Suche | „suche Rechnung KDNR 12393“ | READONLY |
| MailAgent | Mail-Entwürfe steuern | „mail entwerfen“ | STAFF |
| WeatherAgent | Wetter-Stub | „Wetter Berlin“ | READONLY |
| AuthTenantAgent | Mandantenstatus | „welcher Mandant“ | READONLY |
| OpenFileAgent | UI-Aktionen | „öffne <token>“ | READONLY |
| CustomerAgent | Kunde/KDNR | „kunde mit kdnr 123“ | STAFF |
| SummaryAgent | Zusammenfassung (Stub) | „zusammenfassen“ | ADMIN |

### LLMAdapter (Mock)
Kein Ollama/externes LLM in dieser Sprint-Architektur. MockLLM liefert deterministische Antworten für Tests/UI.

## Multi-Tenant Datenmodell
**Ziel**: Mandanten-Scope erzwingen, spätere SaaS-Fähigkeit sicherstellen.

### Tabellen
- `tenants`: tenant_id, display_name
- `tenant_users`: M:N Users ↔ Tenant (Rolle)
- `docs`: tenant_id, kdnr, doctype, doc_date
- `versions`: tenant_id, file_name, file_path
- `entities`: erkannte Entitäten (KDNR, Telefon, E-Mail, Dokumentnummer)
- `links`: optionale Verknüpfungen
- `audit`: tenant_id, action, target

Jede Query im SearchAgent berücksichtigt tenant_id.

## Entity Extraction v1
Regelbasierte Extraktion (keine externen LLMs):
- KDNR
- Dokumentnummern (Rechnung/Angebot/Auftrag)
- Datum
- E-Mail
- Telefon

Diese Entitäten werden in `entities` gespeichert und stehen für strukturierte Suche bereit.

## UI Actions
Agenten können Aktionen zurückgeben, z. B.:
- `open_token`: öffnet Review-Ansicht

UI zeigt passende Buttons/Links im Chat an.

## Erweiterungspunkte
- `LLMAdapter`: späterer Anschluss z. B. OpenAI oder On-Prem
- `EmailProvider`: Dummy + FutureGmailProvider (Stub)
- `WeatherAgent`: Adapter-Pattern

## Security
- Rollenprüfung pro Agent
- Tenant-Scope im Context
- Audit-Log mit tenant_id
