# Competitive Nuggets (Field/Ops) - 2026-02-21

Snapshot type: marketing benchmark synthesis (anbieter claims; intern als hypotheses behandeln).

## 1) Cross-market patterns

### Pattern A: "All-in-one" beats tool-sprawl
- Signals: Meisterwerk, DIGI, etg24, Wowflow all sell consolidation first.
- KUKANILEA implication:
  - Keep "single working inbox" as core narrative (mail/docs/tasks/leads in one flow).
  - Roadmap prioritization should favor end-to-end workflows over isolated feature depth.

### Pattern B: AI wins as triage/automation, not generic chat
- Signals: etg24 inbox assignment/summaries; Rocketta source-backed answers + actions.
- KUKANILEA implication:
  - Prioritize intake automation (classify -> summarize -> route -> draft reply).
  - Require source-citation and action audit trail in every AI-assisted workflow.

### Pattern C: Offline/mobile is purchase-critical in ops
- Signals: Meisterwerk app offline, Wowflow offline-capable, TIME4 mobile field capture.
- KUKANILEA implication:
  - Keep offline-first + sync recovery as explicit release gate.
  - Benchmark "field proof" flow (photo + signature + status + timestamp) as first-class use case.

### Pattern D: Time-to-value benchmarks are aggressive
- Signals: QwikBuild "7 minutes", etg24 3-month trial + fast portal setup, Smoobu 14-day no-card trial.
- KUKANILEA implication:
  - Set measurable activation KPI: first customer + first document + first task + first AI summary in <= 10 minutes.

## 2) Competitor highlights -> KUKANILEA actions

| Provider | High-signal claim (anbieter) | KUKANILEA action |
|---|---|---|
| QwikBuild | idea-to-app in minutes via conversational channel | Add command-style quick actions in chat (`/task`, `/lead`, `/summary`) and measure TTFW |
| etg24 | AI inbox assignment + summaries + trial friction removal | Build "Inbox Triage v1" with deterministic classification and confidence routing |
| Wowflow | tickets + QR/email intake + quick PDF evidence | Add evidence-pack export (photos/events/status) in one click |
| TIME4 / M-SOFT | legal-safe time capture + construction documentation | Strengthen time + site log workflows with compliance-ready exports |
| Meisterwerk | modular all-in-one + offline + accounting integrations | Keep modular packaging narrative but preserve single data model |
| DIGI-SOFTWARE | suite without integration pain; vertical fit in roof/wood | Create vertical template packs (Dach, SHK, Elektro) with default workflows |
| Conntac Entry | check-in/out + location safety monitoring | Add optional check-in/out events with strict privacy controls |
| Memtime | passive timeline capture + DATEV workflow | Introduce activity timeline import/export option for billing context |
| Addigo | digital work report + signature + offer-to-invoice continuity | Prioritize report form templates with signatures and photo evidence |
| Rocketta | M365 data chat + source-based responses + actions | Enforce source citations and action confirmation in AI flows |
| Mendato | cleaning vertical, offline time capture, staff self-service | Reuse for recurring-object workflows and mobile staff UX |
| gigabit.ai | omnichannel AI intake and routing | Extend intake channel adapters with one routing policy engine |
| Smoobu | sync to avoid booking conflicts | Position KUKANILEA as "sync-conflict eliminator" for ops workflows |

## 3) Compliance anchors for release gates

Use these as normative checkpoints in `docs/RELEASE_GATES.md` enforcement:

1. GDPR Art. 25 (privacy by design/default)
- default minimization, role-based access, retention boundaries.

2. GDPR Art. 28 (processor obligations)
- DPA/SCC-ready documentation for support/cloud fallback paths.

3. ePrivacy + consent handling
- no pre-checked tracking; explicit consent for non-essential storage/access.

4. AI Act Art. 50 (transparency)
- explicit UI disclosure when users interact with AI system.

5. eIDAS signature level clarity
- in-app signature classification must not overclaim qualified-signature legal effect.

6. NIS2 supply-chain expectations
- incident runbooks, recovery evidence, dependency hygiene.

## 4) Prioritized experiments (next 4 weeks)

### Experiment E1 - Inbox Triage ROI
- Hypothesis: auto-triage cuts operator handling time >= 30%.
- Measure: time from intake to assigned owner/status before vs after.
- Minimum output: route confidence, fallback queue, audit log.

### Experiment E2 - Time-to-first-workflow
- Hypothesis: new users can finish first end-to-end workflow in <= 10 min.
- Measure: guided setup funnel completion, step drop-off.
- Minimum output: setup wizard telemetry + report.

### Experiment E3 - Evidence Pack
- Hypothesis: one-click report package reduces follow-up clarification loops >= 25%.
- Measure: post-job clarification count and response cycle time.
- Minimum output: PDF/ZIP package with event timeline + attachments + request IDs.

## 5) Risk notes
- All listed performance and savings numbers are provider claims unless independently benchmarked.
- Keep separate labels in product docs: `verified internal metric` vs `external marketing claim`.

## 6) Sources (snapshot list provided by user)
- QwikBuild: https://www.qwikbuild.com/
- etg24: https://etg24.de/ | https://etg24.de/software-testen/ | https://etg24.de/funktionen/e-mail-inbox/
- Wowflow: https://wowflow.com/de/
- TIME4: https://time4.de/
- Meisterwerk: https://www.meisterwerk.app/ | https://apps.apple.com/de/app/meisterwerk-app/id1558856267
- DIGI-SOFTWARE: https://digi-software.de/softwareloesungen-fuer-den-holzbau/
- Conntac Entry: https://entry.conntac.net/ | https://apps.apple.com/de/app/conntac-entry/id6451414291
- Memtime/DATEV: https://www.datev.de/web/de/marktplatz/memtime/
- Addigo: https://addigo.de/loesungen/digitaler-rapportzettel/
- Rocketta: https://rocketta.de/produkte/ki-losungen-fur-sharepoint-microsoft-teams/
- Mendato: https://start.mendato.com/
- gigabit.ai: https://gigabit-ai.de/
- Smoobu: https://www.smoobu.com/de/
- GDPR/AI/eIDAS/NIS2 references: URLs as provided in user research package.
