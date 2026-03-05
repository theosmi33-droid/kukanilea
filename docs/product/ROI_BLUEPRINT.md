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
*Created by Business + Product Lead (Handwerk/SMB) - 2026-03-05*
