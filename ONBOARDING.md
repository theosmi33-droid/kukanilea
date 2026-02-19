# KUKANILEA Onboarding

Stand: 2026-02-17

## Mission
KUKANILEA Systems baut eine lokale, sichere und praxisnahe Betriebsplattform fuer Handwerks- und Service-Teams.

## Business-Plan in Kurzform
- Produkt: Offline-first Betriebsplattform (CRM, Tasks/Kanban, OCR, Inbox/Automation, Wissensbasis).
- Zielgruppe: kleine und mittlere Teams mit hohem Dokumenten- und Kommunikationsaufkommen.
- Nutzenversprechen: weniger manueller Aufwand, mehr Durchlaufgeschwindigkeit, nachvollziehbare Entscheidungen.
- Monetarisierung: Lizenz-/Subscription-Modell pro Team/Tenant mit lokalem Betrieb als Kernangebot.
- Go-to-market: Pilotgruppen (3-5 Teams), danach produktiver Rollout mit klaren DoD-Gates.

## Team und Rollen
Siehe `TEAM_ROLES.md`.

## Systemkontext
- Systemhandbuch (Snapshot, Architektur und Betriebsmodell): `docs/SYSTEMHANDBUCH_v1.md`
- Product-Execution-Plan v2: `docs/PRODUCT_EXECUTION_PLAN_v2.md`
- Marktforschungs-Workspace: `docs/market_research/README.md`
- Pilotbetrieb: `docs/runbooks/pilot_v1.md`
- Pilot-Feedback-Prozess: `docs/pilot_feedback.md`

## Erwartungen an neue Kolleg:innen
Du bist aktiv in vier Rollen:
- Sparringpartner: Architekturen, Risiken, Trade-offs frueh challengen.
- Ideengeber: konkrete Verbesserungen mit Aufwand/Nutzen-Begruendung.
- Marktforscher: Wettbewerber, Standards und Nutzerfeedback faktenbasiert einordnen.
- Qualitaetswaechter: neueste Standards einhalten, Normen/Gesetze/Regelungen in Umsetzung und Review durchsetzen.

Arbeitsstil:
- schnell und praezise liefern
- Entscheidungen messbar machen (Metriken, Tests, Repro-Schritte)
- keine Behauptung ohne belegbare Grundlage

## Technischer Start (Local Dev)
```bash
git clone https://github.com/theosmi33-droid/kukanilea.git
cd kukanilea
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python scripts/seed_dev_users.py
python kukanilea_app.py
```

## Betriebsprinzipien
- Offline-first, tenant-isoliert, default-safe.
- READ_ONLY blockiert Mutationen.
- Keine PII in Eventlog/Telemetry.
- Keine neuen Dependencies ohne ADR.
- Legacy-Schema nur phasenweise migrieren (siehe `docs/runbooks/text_id_migration_plan.md`).
- Postfach (Phase 2): OAuth-ready fuer Google/Microsoft, TLS-only, Versand nur mit expliziter Bestaetigung (`user_confirmed` + Safety-Check).
- Automation Builder (Phase 3/4): Eventlog- und Cron-Trigger, Conditions-Allowlist, pending Actions mit Confirm-Gate, Replay-Schutz, CSRF, per-Rule Rate-Limits, Dry-Run, safe Export/Import sowie Mail-/Webhook-Actions (`email_draft`, confirm-gated `email_send`, allowlist-basierte `webhook`) ohne Auto-Send (siehe `docs/AUTOMATION_BUILDER.md` und `docs/CONFIGURATION.md`).

## Weekly Cadence
- Montag: Planung und Scope-Festlegung
- Mittwoch: Risiko- und Blocker-Check
- Freitag: Review, Kennzahlen, Next Actions

Vorlage: `WEEKLY_TEMPLATE.md`

## Automation Builder v1: Erste Schritte
- Regeln anlegen und pruefen: `/automation`
- Pending Actions pruefen/bestaetigen: `/automation/pending`
- Details und Ausfuehrungslogs: `/automation/<rule_id>` und `/automation/<rule_id>/logs`
- Technische Details, Sicherheitsgrenzen und Beispiel-JSON: `docs/AUTOMATION_BUILDER.md`

## Pilot Quickstart
```bash
python scripts/seed_demo_data.py --tenant-name "DEMO AG"
```

Optionaler Reset der Demo-Daten:
```bash
python scripts/seed_demo_data.py --tenant-name "DEMO AG" --force
```
