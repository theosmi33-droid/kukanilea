# Workflow Templates (Foundation Phase)

## Zweck
`/workflows` stellt eine vereinfachte, produktnahe Sicht auf den bestehenden Automation Builder bereit:
- vordefinierte Template-Installation
- Enable/Disable je Workflow
- Run-Logs ohne PII

## Verfuegbare Templates
- `mail_followup_task`
- `invoice_document_review`
- `task_done_email`

Jedes installierte Template wird intern als Builder-Regel gespeichert und mit
`[workflow_template:<key>]` in der Beschreibung markiert.

## Nutzung
1. Seite `Workflows` oeffnen (`/workflows`).
2. Template installieren.
3. Workflow in der Detailansicht aktivieren.
4. Trigger-Event erzeugen (z. B. Postfach-Eingang oder Task-Move).
5. Logs in `/workflows/<rule_id>` pruefen.

## Sicherheitsregeln
- Workflow-Logs enthalten nur redacted/ID-Referenzen.
- Keine E-Mail-Bodies oder freie Nachrichtentexte in Runner-Kontexten.
- Mail-Actions bleiben fail-closed, wenn Postfach/OAuth/Key nicht verfuegbar ist.

## Troubleshooting
- Workflow installiert, aber keine Runs:
  - Trigger-Event-Typ stimmt nicht.
  - Workflow ist nicht aktiviert.
  - Rule wurde rate-limited.
- `email_send` bleibt pending/failed:
  - Empfaenger nicht in CRM.
  - Kein gueltiger OAuth-Account.
  - Pending-Aktion wurde nicht bestaetigt.
