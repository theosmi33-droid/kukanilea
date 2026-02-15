# KUKANILEA — Project Status & Roadmap

## Stand (Kurzüberblick)
- Offline-first, lokal ausführbar, keine Cloud-Pflicht.
- Multi-Tenant: strikte `tenant_id`-Isolation in Schema und Queries.
- Core-Freeze: additive Änderungen, idempotente DB-Init, keine destruktiven Migrationen.
- Sicherheit: Default-Deny Policies, READ_ONLY-Block, Eventlog-Audit (PII-frei), Input-Limits.
- Determinismus: Tool-/Core-Funktionen mit TX+Retry, no-exec/no-network in kritischen Pfaden.

> Datum/Stand: 2026-02-15 (Europe/Berlin)

## Implementiert (Module & Packages)

| Bereich | Feature/Package | Kernfunktion | Sicherheits-/Qualitätsmerkmale | Doku/ADR |
|---|---|---|---|---|
| Lead Intake Inbox v2 | Gatekeeper, Priority/Pinned, Ownership | Screening-Queue, Priorisierung, Zuständigkeit und Due-Dates | Input-Limits, PII-sichere Events, tenant-safe Queries | [docs/lead_intake.md](docs/lead_intake.md), [0015](docs/decisions/0015-leads-shared-inbox-claims-v1.md) |
| Shared Inbox Claims v1 | Claim/Release/Force/Expire TTL | Exklusive Bearbeitung mit Ablauf und Kollisionserkennung | READ_ONLY für Mutationen, Claims tenant-safe, Audit-Events | [docs/leads_shared_inbox_claims.md](docs/leads_shared_inbox_claims.md), [0015](docs/decisions/0015-leads-shared-inbox-claims-v1.md) |
| Automation & Daily Insights v1 | Rules + Insights Cache | Allowlisted DSL, Run-Audit, Metriken (unclaimed/expiring/collisions) | Loop-Guards, deterministische Limits, PII-freie Payloads | [docs/automation_insights.md](docs/automation_insights.md), [0011](docs/decisions/0011-automation-insights-v1.md) |
| Security UA Hash (HMAC) | Telemetrie-Härtung | Kollisionstelemetrie ohne Roh-UA | HMAC statt Plain Hash, schluesselbasiert, best-effort | [docs/automation_insights.md](docs/automation_insights.md) |
| Lead Guard Decorator v1 | Zentraler Zugriffsschutz | Einheitliche Guard-Logik für mutierende Lead-Routen | Konsistente 403, Coverage-Test gegen vergessene Routen | [docs/leads_shared_inbox_claims.md](docs/leads_shared_inbox_claims.md) |
| Knowledge Base v1 (FTS5) | Chunks, Policies, Suche | Tenant-sichere Wissensablage + FTS/LIKE-Fallback | Redaction vor Persistenz, Default-Deny Policies, PII-freie Events | [docs/knowledge_base.md](docs/knowledge_base.md), [0012](docs/decisions/0012-knowledge-base-v1-fts5.md) |
| Knowledge Email Source v0 | Policy-gated `.eml` Ingest | Upload, Dedup, redigierte Chunks | stdlib-only Parser, Größenlimits, keine Attachmentspeicherung | [docs/knowledge_email_source_v0.md](docs/knowledge_email_source_v0.md), [0013](docs/decisions/0013-knowledge-email-source-v0.md) |
| Entity Links v0 + Coverage/Titles | Universelle Verknüpfung | Canonical Links, sichere Titelauflösung, Panel-Integration | Self-link/duplicate Guards, sanitize allowlist, kein `|safe` | [docs/entity_links.md](docs/entity_links.md), [0014](docs/decisions/0014-entity-links-v0.md) |
| Lead Conversion v0 | Lead → Deal → Quote | Confirm-first Flow mit `converted_from` Links | Guard-enforced, keine stille PII-Übernahme, PII-freie Events | [docs/lead_intake.md](docs/lead_intake.md) |
| Knowledge ICS Source v0 | Policy-gated `.ics` Ingest | VEVENT-Parser (DTSTART/DTEND/SUMMARY/LOCATION) | Unfolding, harte Limits, RRULE/ATTACH ignoriert, keine Raw-ICS-Speicherung | [docs/knowledge_ics_source_v0.md](docs/knowledge_ics_source_v0.md), [0016](docs/decisions/0016-knowledge-ics-source-v0.md) |
| CI Hardening + Security Regression Suite v1 | CI + Guardrail-Tests | Triage-Standard + Security-Subset | Least-Privilege CI, no-`|safe`, forbidden imports, eventlog-key checks | [docs/ci.md](docs/ci.md), [docs/prompts/03-ci-hardening-security-suite-v1.md](docs/prompts/03-ci-hardening-security-suite-v1.md) |

## Core-Freeze Leitplanken (Was ist „heilig“?)
- DB ist Source of Truth; Schemaänderungen sind additiv und idempotent.
- Dateisystem ist operative Realität, aber Identität/Ownership/ACL werden in der DB entschieden.
- Agenten/Automation schlagen vor; destruktive oder sensible Aktionen bleiben explizit kontrolliert.
- Tool-Grenzen bleiben allowlisted; kein beliebiges Ausführen von Code/Kommandos.
- Multi-Tenant-Isolation ist verpflichtend (`tenant_id` in Tabellen + `WHERE`-Filtern).
- READ_ONLY blockiert alle Mutationen konsistent in Core und Route-Layer.
- Eventlog ist für Mutationen verpflichtend, aber ohne PII.

## Sicherheits- & Qualitätsmaßnahmen (Was verhindert Rückfälle?)
- CI nutzt `triage --ci --fail-on-warnings` mit stabiler Ignore-Regex für bekannte Fremdbibliotheks-Warnings.
- Security-Regressionstests decken ab:
  - kein `|safe` in Templates,
  - keine verbotenen Imports/Exec-Pfade in sensitiven Modulen,
  - keine PII-ähnlichen Keys in Eventlog-Payloads.
- UA-Telemetrie ist HMAC-basiert; Schluessel-Rotation reduziert absichtlich Korrelation über Zeit.
- Lead-Guard-Decorator zentralisiert Zugriffsregeln; Coverage-Test verhindert ungeschützte neue Routen.
- ICS-Ingest ist strikt begrenzt (Bytes/Events/Felder), mit Unfolding und ohne Rohdatenpersistenz.

## Merge-Runbook (PR Reihenfolge)
1. PR03: CI-Härtung + Security Regression Suite.
2. PR04: Lead Conversion v0.
3. PR05: Knowledge ICS Source v0.

**Warum diese Reihenfolge:** erst Sicherheits-/Qualitätsnetz, dann Business-Mutation-Flow, danach parserlastige Quelle mit höherem Edge-Case-Risiko.

**Nach jedem Merge:**
1. `pytest -q`
2. `python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"`

**Manuelle Smoke-Checks (Kurz):**
1. Claim-Kollision erzeugen und prüfen, dass Mutation blockiert wird und Collision-Metrik sichtbar bleibt.
2. Lead-Conversion confirm-first durchlaufen; Guard/READ_ONLY-Verhalten validieren.
3. ICS-Policy OFF/ON testen; Upload, Suche und negative Fixtures (ATTACH/RRULE) prüfen.

**Externe Referenzen (Pattern/Leitlinien):**
- GitHub Actions Security (Least Privilege): [GitHub Docs](https://docs.github.com/actions/security-for-github-actions)
- Collision Detection in Team-Inboxes: [Help Scout](https://docs.helpscout.com/article/99-prevent-duplicate-replies-with-collision-detection)
- iCalendar/ICS Spezifikation (Unfolding): [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545)
- Usability-Pilotumfang („5 Users“): [Nielsen Norman Group](https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/)

## Roadmap (Nächste Meilensteine)

### Kurzfristig (0–2 Wochen)
- Pilotphase mit 3–5 Nutzern über 2 Wochen (Fokus: Inbox-Claims, Conversion, ICS-Ingest).
- Falls noch nicht vorhanden: `TODO` Runbook unter `docs/runbooks/pilot_v0.md` anlegen.

### Mittelfristig (2–8 Wochen)
- Invoicing/DATEV-Export (cent-basiert, auditierbar, tenant-safe).
- Gatekeeper/Triage-Feinschliff auf Basis Pilotmetriken.
- Skills ADR + lokales Skill-Registry-Design (security-first, declarative allowlists).

### Langfristig
- Mobile Ausbau (PWA-first, ggf. native Hülle).
- Erweiterte AI-Funktionen (erklärbar, deterministisch, strikt opt-in).
- Skills-Marketplace nur nach belastbarem Security-Modell.

| Horizont | Ziel | Outcome/Metric | Risiken | Mitigation |
|---|---|---|---|---|
| 0–2 Wochen | Pilot stabil fahren | Nutzungsquote, Kollisionen/Tag, Durchlaufzeit Lead→Quote | Scope-Drift im Pilot | Feste Testskripte, tägliche Triage |
| 2–8 Wochen | Umsatzpfad operationalisieren | Anzahl konvertierter Leads, Angebotsdurchlaufzeit | Inkonsistente Datenflüsse | Guard- und Eventlog-Checks, Smoke-Runbook |
| Langfristig | Plattform skalieren | Mandantenfähigkeit unter Last, sichere Erweiterbarkeit | Komplexität/Angriffsfläche | Paketweise Releases, Security Regression als Gate |

## Externe Inspiration & Abgrenzung (Patterns vs. Pitfalls)
- Übernommene UX-Patterns: Gatekeeper, Priorität, Shared Inbox Ownership, Collision Detection.
- Bewusste Abgrenzung: keine ausführbaren Dritt-Skripte, keine unsicheren Runtime-Plugins.
- Für Skills/Automation gilt weiterhin: deklarativ, allowlisted, auditierbar, tenant-safe.

## See also
- [ROADMAP.md](ROADMAP.md)
- [docs/prompts/README.md](docs/prompts/README.md)

## Appendix: Dokuliste (Schnellnavigation)
- Kern-Dokus:
  - [docs/lead_intake.md](docs/lead_intake.md)
  - [docs/leads_shared_inbox_claims.md](docs/leads_shared_inbox_claims.md)
  - [docs/automation_insights.md](docs/automation_insights.md)
  - [docs/knowledge_base.md](docs/knowledge_base.md)
  - [docs/knowledge_email_source_v0.md](docs/knowledge_email_source_v0.md)
  - [docs/knowledge_ics_source_v0.md](docs/knowledge_ics_source_v0.md)
  - [docs/entity_links.md](docs/entity_links.md)
  - [docs/ci.md](docs/ci.md)
- ADRs:
  - [docs/decisions/0009-lead-inbox-v2-gatekeeper-priority-ownership.md](docs/decisions/0009-lead-inbox-v2-gatekeeper-priority-ownership.md)
  - [docs/decisions/0011-automation-insights-v1.md](docs/decisions/0011-automation-insights-v1.md)
  - [docs/decisions/0012-knowledge-base-v1-fts5.md](docs/decisions/0012-knowledge-base-v1-fts5.md)
  - [docs/decisions/0013-knowledge-email-source-v0.md](docs/decisions/0013-knowledge-email-source-v0.md)
  - [docs/decisions/0014-entity-links-v0.md](docs/decisions/0014-entity-links-v0.md)
  - [docs/decisions/0015-leads-shared-inbox-claims-v1.md](docs/decisions/0015-leads-shared-inbox-claims-v1.md)
  - [docs/decisions/0016-knowledge-ics-source-v0.md](docs/decisions/0016-knowledge-ics-source-v0.md)
