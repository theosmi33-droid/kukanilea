# KUKANILEA Product Execution Plan v2

Stand: 2026-02-18

Dieses Dokument ueberfuehrt den integrierten Markt- und Produktentwicklungsplan in umsetzbare Artefakte im Repository.

## 1) Produktziel
KUKANILEA liefert ein lokales Business-OS mit CRM, Postfach, Automation, OCR und KI-Unterstuetzung. Kernprinzipien:
- Offline-first
- Tenant-Isolation
- Security-by-default
- Nachvollziehbarkeit via Eventlog

## 2) Technische Schwerpunkte

### Lizenzmodell (v2)
- Signierte Offline-Lizenz bleibt Primärquelle.
- Optionale Online-Validierung mit:
  - Intervallpruefung (`KUKANILEA_LICENSE_VALIDATE_INTERVAL_DAYS`)
  - Grace-Fenster (`KUKANILEA_LICENSE_GRACE_DAYS`)
  - lokalem Cache (`KUKANILEA_LICENSE_CACHE_PATH`)
- Fail-closed nach Grace-Ablauf.

### Postfach / Sicherheit
- Credential-/Token-Encryption ueber `EMAIL_ENCRYPTION_KEY`.
- Versand nur confirm-gated.
- Webhooks: HTTPS + Domain-Allowlist + Timeout + Retry-Limit.

### Automation
- Trigger: Eventlog + Cron
- Conditions: declarative allowlist
- Actions: draft-first, riskante Actions pending-confirm

## 3) Marktforschung im Repo
Arbeitsbereich unter `docs/market_research/`:
- `competitor_profile_template.md`
- `competitor_matrix.csv`
- `weekly_research_plan.md`
- `profiles/`

Validierung:

```bash
python -m app.devtools.market_research --matrix docs/market_research/competitor_matrix.csv --json
```

## 4) Priorisierte Deliverables
1. Wettbewerbermatrix (14 Tools) vervollstaendigen
2. UI/UX-Benchmark reporten (Inbox/OCR/Kanban/Mobile)
3. Compliance-Gap-Liste (DSGVO/GoBD) mit konkreten Tasks
4. Lizenz-/Pricing-Entscheidung in Produkt-Roadmap ueberfuehren
5. Telefon-Agent-Strategie (Cloud-first optional, lokal spaeter)

## 5) Definition of Done (v2)
- Matrix validiert (keine Fehler)
- Prioritaet-HIGH Tools mit Quellen belegt
- Lizenz-Flow (lokal + online/grace) getestet
- Security-Gates gruen
