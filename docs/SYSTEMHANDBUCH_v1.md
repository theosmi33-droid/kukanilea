# KUKANILEA Systemhandbuch v1

**Stand (Snapshot):** 2026-02-22  
**Repository:** `/Users/gensuminguyen/Tophandwerk/kukanilea-git`  
**Status:** Feature Complete (0-110% Master Path)

Hinweis: Dieses Dokument ist ein Snapshot. Zahlen und Betriebszustaende (Tests, CI, offene PRs, Route-Anzahl) koennen sich nach dem Snapshot-Commit aendern.

## Inhaltsverzeichnis
1. [Einleitung und Vision](#1-einleitung-und-vision)
2. [Architekturueberblick](#2-architekturueberblick)
3. [Datenmodell und Persistenz](#3-datenmodell-und-persistenz)
4. [Mandantenmodell (Tenant-Isolation)](#4-mandantenmodell-tenant-isolation)
5. [Sicherheitsmodell](#5-sicherheitsmodell)
6. [Funktionsbloecke (Module)](#6-funktionsbloecke-module)
7. [Lizenz- und Betriebslogik](#7-lizenz--und-betriebslogik)
8. [Qualitaet, CI und Engineering-Disziplin](#8-qualitaet-ci-und-engineering-disziplin)
9. [Aktueller Zustand und Ausblick](#9-aktueller-zustand-und-ausblick)
10. [Verantwortlichkeiten pro Modul](#10-verantwortlichkeiten-pro-modul)
11. [Datenflussdiagramm (Mermaid)](#11-datenflussdiagramm-mermaid)
12. [Glossar](#12-glossar)
13. [Pflege und Aenderungsprozess](#13-pflege-und-aenderungsprozess)

## 1. Einleitung und Vision
KUKANILEA ist ein lokal laufendes, mandantenfaehiges Betriebs- und Kommunikationssystem fuer Handwerks- und Service-Teams. Es vereint CRM, Lead-Intake, Postfach, Automationen, OCR/Wissensbasis, Tasks, Zeit und Audit in einer Offline-first-Anwendung auf Basis von SQLite.

**Vision:** Eingehende Informationen (E-Mails, Dokumente) schnell in strukturierte Arbeit uebersetzen - von der Nachricht zum nachvollziehbaren Arbeitsfluss, sicher, auditierbar und ohne Cloud-Zwang. 

**Kernversprechen:** "Time-to-First-Value" unter 3 Minuten durch branchenspezifische Vertical Kits (Dachbau, SHK, Facility) und sichere KI-Assistenz.

## 2. Architekturueberblick
- Backend: Python 3.11+ mit Flask (monolithisch, modular strukturiert)
- Datenbank: SQLite (Core-DB + Auth-DB)
- Frontend: Jinja2-Templates, HTMX, Tailwind CSS (kein React/Vue/Alpine)
- Lokaler Server: `127.0.0.1:5051`
- App-Entrypoint: `kukanilea_app.py`
- App-Fabrik: `app/__init__.py`
- Konfiguration: `app/config.py`

Wesentliche Module (Erweitert):
- `app/observability`: Structured Logging & OTel
- `app/autonomy`: Database Healer & Degraded Mode
- `app/ai_chat`: Human-in-the-Loop AI Assistant
- `app/seeder.py`: Vertical Kit Injection

## 3. Datenmodell und Persistenz
- Core-Schema: `kukanilea_core_v3_fixed.py`
- Domainentabellen u. a. fuer:
  - Users, Roles, Audit
  - Tasks, Time, Events
  - Customers, Contacts, Deals, Quotes
  - Leads, Claims
  - Knowledge, OCR-Jobs, Policies
  - Automation Rules, Triggers, Conditions, Actions
  - Tags, Entity Links
  - Documents, Versions
  - Tenants
- Auth-DB separat fuer Authentifizierung/Sessions
- Benutzerdaten (macOS): `~/Library/Application Support/KUKANILEA/`

**Neu:** 
- `entities`: Universelle Tabelle für Vertical Seeding (UUID Primary Key)
- `autonomy_ocr_jobs`: Tracking für OCR-Prozesse

Grundprinzipien:
- TEXT-IDs (UUID) statt Integer-Autoinkrement (konsequent umgesetzt)
- Tenant-Scoping im Datenzugriff
- Eventlog als Audit-Rueckgrat fuer Mutationen

## 4. Mandantenmodell (Tenant-Isolation)
- Kernprinzip: Tenant-bezogener Zugriff (`tenant_id`-basiert)
- Default-Tenant/Fixierung konfigurierbar
- **Vertical Seeding:** Mandantenspezifische Dateninitialisierung (`app/seeder.py`) respektiert strikte Isolation.

## 5. Sicherheitsmodell
- Read-only-Modus blockiert serverseitig mutierende HTTP-Methoden
- **Degraded Mode:** Bei DB-Korruption schaltet das System automatisch in einen Schutzmodus (nur GET erlaubt).
- **Privacy-First Logs:** JSON-Logs hashen Tenant-IDs und enthalten keine PII/Payloads.
- **Sichere KI:** "Conversation as a Shortcut" nutzt KI nur als Parser. Schreibvorgänge erfordern explizites Nutzer-Bestätigen (Confirm-Gate). Keine "Agenten-Wildnis".
- Keine PII in Eventlog/Telemetry
- Secrets/Tokens ueber den bestehenden Verschluesselungsmechanismus
- CSRF-Schutz fuer mutierende Web-Requests

## 6. Funktionsbloecke (Module) - Update

### 6.1 Lead Intake & CRM
- Eingang, Priorisierung, Konvertierung von Anfragen
- Kunden, Kontakte, Deals, Angebote

### 6.2 Postfach-Hub & Omni
- IMAP/SMTP + OAuth, Kanalabstraktion

### 6.3 Automation Builder
- Trigger: Eventlog, Cron
- Conditions: deklarativ, allowlist-basiert
- Actions: Tasks/Followups/Drafts/Mail/Webhook

### 6.4 Knowledge / OCR / Autonomy (Enhanced)
- **OCR:** Tesseract-Integration mit dynamischer Pfad-Auflösung (`shutil.which`) und Pre-Processing (Pillow) für robuste Erkennung.
- **Maintenance:** Automatischer `quick_check` beim Start. Manuelles `VACUUM` via CLI.
- **Healer:** Degraded Mode Middleware mit Content Negotiation (HTML Error Shell für UI, JSON für API).

### 6.5 AI & Chat (Neu)
- **AI Assistant:** `/ai-chat` Interface.
- **Intent Parsing:** Lokale Erkennung von Shortcuts (z.B. "Aufgabe: Dachrinne").
- **Human-in-the-Loop:** KI generiert HTMX-Formulare, Nutzer speichert.
- **Diagnostics:** Read-Only Diagnose-Agent analysiert Logs lokal (Ollama) und erstellt Diff-Vorschläge (AI Act Art. 50 konform).

### 6.6 Vertical Kits (Neu)
- **Seeding:** Sofortige Befüllung der DB mit Branchen-Templates (Dach, SHK, Facility).
- **Time-to-Value:** Fertige Aufgaben und Workflows direkt nach Onboarding.

### 6.7 Observability (Neu)
- **Logging:** Strukturiertes JSON-Format, `X-Request-ID` Tracing.
- **Metrics:** Optionales OpenTelemetry (lokal, Console Exporter).
- **Benchmarking:** Reproduzierbare SQLite-Performance-Tests (WAL/NORMAL Trade-off dokumentiert).

## 7. Lizenz- und Betriebslogik
- Lokale Trial-/Lizenzpruefung
- Betriebsmodi: write-enabled vs. read-only vs. degraded

## 8. Qualitaet, CI und Engineering-Disziplin
**Release Gates (Härtung):**
- **Q-TEST:** Lokale Tests ohne hartkodierte Pfade (`pathlib`).
- **CI-ENV:** GitHub Actions mit Tesseract-Integration und Nightly-Schedule (UTC).
- **Q-PERF:** SQLite Benchmark (P99 Latency Gates).
- **Q-SCAN:** AI Intent Parser Verification.

Lokale Verify-Gates:
- `python -m compileall -q .`
- `ruff check .`
- `pytest -q`
- `python scripts/benchmark_db.py ...`

## 9. Aktueller Zustand und Ausblick
**Status:** System ist Feature-Complete für den MVP-Release (110% Vision).
- Alle Core-Module implementiert und getestet.
- Compliance-Anforderungen (GDPR, AI Act) technisch verankert.
- CI/CD stabilisiert.

## 10. Verantwortlichkeiten pro Modul (Update)
| Modul | Hauptverantwortlichkeiten | Wichtige Pfade |
|---|---|---|
| Observability | Logging, Metrics, Tracing | `app/observability/` |
| Autonomy | Maintenance, Healer, OCR | `app/autonomy/` |
| AI Chat | Intent Parsing, Assistant UI | `app/ai_chat/` |
| Seeding | Vertical Kits, DB Injection | `app/seeder.py`, `app/verticals.py` |
| Web/UI | Routen und Templates | `app/web.py`, `templates/` |
| Core | DB-Schema, Auth, Config | `app/__init__.py`, `app/database.py` |

## 11. Datenflussdiagramm (Mermaid) - AI Integration
```mermaid
flowchart TD
    User[Benutzer] -->|Eingabe| Chat[AI Chat Interface]
    Chat -->|Text| Parser[Intent Parser (Regex/Local LLM)]
    Parser -->|Struktur| HTMX[HTMX Formular Generator]
    HTMX -->|Vorschlag| User
    User -->|Bestätigung (Klick)| Router[App Router (z.B. /tasks/new)]
    Router -->|Schreibzugriff| DB[(SQLite DB)]
    DB -->|Log| Eventlog
    Eventlog -->|Trigger| Automation
```

## 12. Glossar
- **Degraded Mode:** Read-Only Zustand bei erkannten Integritätsverletzungen.
- **Vertical Kit:** Vorkonfiguriertes Datenpaket für eine spezifische Branche.
- **Confirm-Gate:** UX-Pattern, das KI-Handlungen stoppt, bis der Nutzer explizit bestätigt.
- **Tenant:** Mandant mit isolierten Datenzugaengen
- **Eventlog:** auditierbare Mutationseintraege

## 13. Pflege und Aenderungsprozess
- Eigentum: Architektur-/Maintainer-Kreis
- Updates erfordern Evidence (Benchmark, Tests, Logs).
