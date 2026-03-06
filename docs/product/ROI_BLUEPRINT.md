# ROI BLUEPRINT: KUKANILEA for Handwerk/SMB

**Goal:** Reduce administrative overhead by 40% and increase quote close rate by 20% through prioritized, AI-assisted workflows.

---

## 1. Top 10 Pain Points & Solutions

| # | Pain Point | User Story | Tool (Domain) | UI Lane | First PR Candidate | Success Metric |
|---|------------|------------|---------------|---------|---------------------|----------------|
| 1 | **Speed-to-Lead** | As a contractor, I want to respond to web/mail inquiries in <15 mins to beat competitors. | `Emailpostfach` | `messenger` | `app/templates/messenger.html` | TFR < 15m |
| 2 | **Quoting Speed** | As a business owner, I want to turn a voice memo/sketch into a PDF quote on-site. | `Upload` | `upload` | `app/templates/upload.html` | QCT < 2h |
| 3 | **Site Diary** | As a site manager, I want to log defects/progress with photos that auto-sync to the project. | `Projekte` | `aufgaben_projekte` | `app/templates/projekte/` | Log time < 5m |
| 4 | **Instant Billing** | As a technician, I want to invoice immediately after customer signature on-site. | `Visualizer` | `system_pages` | `app/templates/visualizer.html` | DSO reduction |
| 5 | **Time Tracking** | As an employee, I want a one-tap start/stop for my current task to ensure 100% billing. | `Zeiterfassung` | `dashboard` | `app/templates/dashboard.html` | TTC > 95% |
| 6 | **Quote Follow-up** | As a sales lead, I want auto-reminders for quotes that haven't been accepted in 3 days. | `Projekte` | `automation` | `app/templates/automation/` | Close Rate +15% |
| 7 | **Scheduling** | As an office admin, I want to see technician availability at a glance to fill emergency gaps. | `Kalender` | `kalender` | `app/templates/calendar.html` | Zero double-bookings |
| 8 | **Material Search** | As a craftsman, I want to scan a part and find the best price from regular suppliers. | `Upload` | `upload` | `app/api.py` | Material cost -5% |
| 9 | **Comm History** | As a owner, I want a single timeline for WhatsApp, Mail, and Phone calls per customer. | `Messenger` | `messenger` | `app/templates/messenger.html` | 100% visibility |
| 10 | **Payment Chasing**| As an accountant, I want auto-WhatsApp reminders for overdue invoices. | `Messenger` | `automation` | `app/templates/automation/` | DSO -20% |

---

## 2. The 3 Killer Flows (MVP Scope)

### Flow A: "Lead-to-Quote Fast Lane"
- **Workflow:** Mail inquiry -> AI extraction of items/prices -> Draft Quote in Visualizer -> Send via WhatsApp.
- **Data Model:** `crm_contacts`, `quotes`, `quote_items`.
- **MVP:** Auto-drafting from PDF attachments or email body using W02 (Extraction).

### Flow B: "Field-to-Invoice One-Tap"
- **Workflow:** Task "Done" in app -> Generate Work Report -> Customer signs on tablet -> Auto-Invoice.
- **Data Model:** `tasks`, `work_reports`, `signatures`, `invoices`.
- **MVP:** Basic HTML-to-PDF generation with local signature capture.

### Flow C: "Smart Follow-Up Engine"
- **Workflow:** If `quote.status == 'pending'` for > 72h -> AI generates personal follow-up -> User confirms -> Sent.
- **Data Model:** `automation_triggers`, `communication_logs`.
- **MVP:** Dashboard widget "Stale Quotes" with "Remind Now" button (Confirm Gate).

---

## 3. Instrumentation Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **TFR** | Time-to-First-Response: Duration between inquiry arrival and first reply. | < 15 Minutes |
| **QCT** | Quote Cycle Time: Duration from lead arrival to quote sent. | < 4 Hours |
| **DSO** | Days Sales Outstanding: Average time to receive payment after invoicing. | < 14 Days |
| **TTC** | Time Tracking Completeness: % of working hours mapped to tasks. | > 98% |

---

## 4. Engineering Standards & Guardrails

### Acceptance Criteria (AC)
- All workflows must work **offline** (cached data, local AI if available).
- Risk-heavy actions (Send, Delete, Invoice) must have a **Confirm Gate**.
- UI must adhere to **White-Mode Only** and **Zero-CDN** (local assets).
- Every domain action must trigger an **Audit Log** (Who, When, What).

### Test Ideas
- **Unit:** Mock AI extraction with malformed PDF to ensure graceful degradation.
- **Integration:** Trigger automation on a 73-hour-old quote and verify the dashboard alert.
- **E2E:** Complete the "Field-to-Invoice" flow and verify PDF generation without internet.

### Do-Not-Do (Scope Killers)
- DO NOT build a complex accounting engine (Export to Lexware/DATEV instead).
- DO NOT use external cloud storage for customer photos (Local-first + sync).
- DO NOT bypass the domain ownership (e.g., `upload` tab must not write directly to `invoices` table).

---
## 5. Gewerke Scenarios (All Trades Coverage)

### Scenario Matrix by Trade

| Gewerk | Typical Trigger | Must-Automate Outcome | KPI |
|--------|------------------|-----------------------|-----|
| Elektro | Störungsmeldung + Foto im Chat | Task + Termin + Materialhinweis | TFR, TTC |
| SHK | Wartung fällig + Seriennummer | Wartungsauftrag + Prüfliste + Terminfenster | QCT, TTC |
| Dach | Schadensfoto nach Wetterereignis | Mängelbericht + Nachtragsvorschlag | QCT, DSO |
| Maler | Angebotsanfrage mit Flächenangabe | Positionsliste + Angebotsentwurf | QCT |
| Fensterbau | Reklamation nach Montage | Ticket + Gewährleistungsakte + SLA-Reminder | TFR |
| Schreiner | Maßauftrag mit Skizze/PDF | Projektmappe + Materialliste + Terminplan | TTC |
| Metallbau | Änderungswunsch während Ausführung | Change-Task + neue Kalkulationsposition | QCT, DSO |
| Gartenbau | Saisonauftrag mit wiederkehrenden Terminen | Serienplanung + Ressourcenblöcke | TTC |
| Tiefbau | Baustellenprotokoll + Behinderungsanzeige | Bautagebuch + Claim-Nachweis | DSO |
| Glasfaser/Bau | Mehrere Standorte pro Auftrag | Multi-Route + Teamzuweisung + Tagesreport | TTC |

### Trade-Neutral Workflow Rules
- Every inbound request must be normalized to: `contact`, `location`, `scope`, `urgency`, `attachments`.
- Every write action must require explicit confirm (`confirm_required = true`).
- Every work completion must produce an auditable artifact (report, signature, invoice draft).
- Every reminder workflow must be idempotent and tenant-scoped.

---
## 6. KPI Instrumentation Blueprint

### Event Model (Minimal)

| Event | Producer | Required Fields |
|------|----------|-----------------|
| `lead.received` | Mail/Messenger/Phone intake | `tenant_id`, `channel`, `received_at` |
| `lead.responded` | Messaging/Email send flow | `tenant_id`, `response_at`, `lead_id` |
| `quote.created` | Visualizer/Upload flow | `tenant_id`, `quote_id`, `created_at` |
| `quote.sent` | Messenger/Email | `tenant_id`, `quote_id`, `sent_at` |
| `task.started` | Aufgaben/Zeiterfassung | `tenant_id`, `task_id`, `user_id`, `ts` |
| `task.completed` | Aufgaben/Projekte | `tenant_id`, `task_id`, `ts` |
| `invoice.sent` | Billing flow | `tenant_id`, `invoice_id`, `sent_at` |
| `payment.received` | Finance sync/manual | `tenant_id`, `invoice_id`, `paid_at` |

### Derived KPI Queries (MVP)
- `TFR`: `avg(lead.responded.response_at - lead.received.received_at)`
- `QCT`: `avg(quote.sent.sent_at - lead.received.received_at)`
- `DSO`: `avg(payment.received.paid_at - invoice.sent.sent_at)`
- `TTC`: `(tracked_work_seconds / planned_work_seconds) * 100`

### Dashboard KPI Contracts
- `/api/dashboard/summary` must expose KPI card placeholders for `TFR`, `QCT`, `DSO`, `TTC`.
- KPI payload must include `value`, `period`, `trend`, `source_quality`.
- Missing data must degrade gracefully (`status=degraded`) instead of hard failing.

---
## 7. Rollout Plan by Maturity

### Phase 1 (Weeks 1-2): Core Intake + Task Integrity
- Enable mail/messenger intake normalization for all tenants.
- Enforce confirm gate on every write-like action.
- Track baseline TFR and daily task throughput.

### Phase 2 (Weeks 3-4): Quote + Field Documentation
- Add quote draft generation from uploads and structured notes.
- Activate field diary + defect capture in project timeline.
- Begin measuring QCT per trade.

### Phase 3 (Weeks 5-6): Billing + Follow-up Automation
- Add invoice draft trigger from `task.completed`.
- Enable stale quote reminders with explicit user confirm.
- Start DSO and reminder conversion tracking.

### Exit Criteria for Productive Rollout
- At least 90% of inbound requests are normalized without manual retyping.
- At least 80% of finished tasks produce a report artifact.
- At least 70% of overdue invoices trigger reminder workflow.
- At least one KPI trend per tenant is visible in Dashboard.

---
## 8. UX Acceptance Checklist (White-Mode / Local-First)

- White-mode remains default and visually consistent across dashboard, messenger, upload, projects.
- No CDN dependency for charts, fonts, icons, or JS runtime.
- Mobile viewport supports one-thumb operation for: start timer, add note, capture photo, confirm action.
- Error states are actionable: every failed action gives retry path + audit reference ID.

### UX Smoke Tests
1. Create lead from messenger text with attachment metadata.
2. Convert lead into task and calendar proposal with confirm gate.
3. Complete task and verify report artifact appears in project context.
4. Trigger quote follow-up reminder and verify explicit confirm step.
5. Open dashboard and verify KPI cards render without network calls.

---
*Created by Business + Product Lead (Handwerk/SMB) - 2026-03-05*
