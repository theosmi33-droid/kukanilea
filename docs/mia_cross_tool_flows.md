# MIA Cross-Tool Flows (ROI Batch 1)

Diese Iteration liefert **5 produktionsnahe Cross-Tool-Flows** auf Basis registrierter Actions mit Confirm-Gates und Audit-Punkten.

## Flow-Modell

Implementiert in `app/core/mia_cross_tool_flows.py`:

- **Registry-first:** Jeder Step referenziert nur Actions aus `DEFAULT_ACTIONS`.
- **Confirm-Gate:** Jeder write-Step (`create_*`, `queue_local_review`) wird als `confirm_required=true` geplant.
- **Audit-Evidence:** Jede Proposal-/Execution-Phase schreibt MIA-Audit-Einträge (`mia.proposal.created`, `mia.confirm.requested`, `mia.execution.started`, `mia.execution.finished`, `mia.confirm.denied`).
- **Missing Context:** Fehlende Kontextdaten wechseln den Step in `mode=propose` + `reason`, statt blind zu schreiben.
- **Offline Degradation:** Bei fehlendem Suchindex wird lokal auf `queue_local_review` degradiert.

## Gebaute Flows

1. **E-Mail → Aufgabe (`email_to_task`)**
   - Trigger: `email.received` mit TODO-/Aufgaben-Signal.
   - Actions: `create_task`.
   - ROI: schneller Intake aus Mailbox in operative Aufgabenliste.

2. **E-Mail → Termin-Vorschlag (`email_to_meeting_proposal`)**
   - Trigger: `email.received` mit Termin-/Meeting-Signal.
   - Actions: `suggest_meeting_slots`, `create_calendar_event`.
   - Missing Context: ohne `suggested_start` bleibt Termin-Step im Propose-Modus.

3. **Messenger → Follow-up-Aufgabe (`messenger_to_followup_task`)**
   - Trigger: `messenger.received` mit Follow-up-Signal.
   - Actions: `create_followup_task`.
   - Missing Context: ohne `thread_id` nur Proposal.

4. **Dokument → Frist/Aufgabe (`document_to_deadline_task`)**
   - Trigger: `document.processed` mit Frist-/Deadline-Indiz.
   - Actions: `create_task`.
   - Missing Context: ohne `detected_deadline` nur Proposal.

5. **Rechnung/Beleg → Suche/Zusammenfassung/Folgeaktion (`invoice_receipt_triage`)**
   - Trigger: `document.processed` mit Rechnungs-/Beleg-Signal.
   - Actions: `search_documents` oder `queue_local_review` (degradiert), `summarize_document`, `create_followup_task`.
   - Missing Context: ohne `amount_due` wird Folgeaktion nur vorgeschlagen.

## Technische Risiken

- **Semantische Trigger-Heuristiken:** Keyword-Matching kann falsch-positive Flows triggern.
- **Action-Handler-Abdeckung:** Nicht registrierte/fehlende Handler laufen aktuell als `simulated` oder `blocked`.
- **Audit-Persistenz:** Audit-Evidence liegt im Engine-Log (in-memory); Persistenz-Anbindung kann im nächsten Schritt ergänzt werden.
- **Context-Qualität:** Qualität der Frist-/Termin-Erkennung hängt von Upstream-OCR und Intake-Normalisierung ab.
