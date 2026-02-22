# KUKANILEA – Vollständiger Pfad von 0% → 100% (Release-reif) und 110% Vision

**Die 110%-Vision (Nordstern):**
KUKANILEA ist ein local-first Business OS für operative Teams, das täglich „den Laden am Laufen hält“. Nicht nur „Features“, sondern ein zuverlässiger Arbeitsraum mit auditierbarer Sicherheit. Der Unterschied zu typischen SaaS: **Offline-first, Daten bleiben lokal, harte Mandanten-Isolierung, Evidence-Pack-Gates, Compliance-by-default (EU).**

---

## 0% → 15%: Mission & Architektur-Fundament (Status: ✅ Done)
1. **Zielgruppe:** Dach/SHK/Elektro (Primärsegment).
2. **Value Prop:** Lokales Betriebs-OS ohne Cloud-Zwang.
3. **Moat:** Offline-first + Evidence-Gates + Update-Trust + Compliance-Nachweise.
4. **Architektur:** Python Backend, HTMX UI, SQLite+FTS, Local Storage.
5. **Security Model:** Deny-by-default, Tenant-Isolation, CSP.
6. **Error Shell:** Niemals Raw JSON, immer Recovery.

## 15% → 35%: Kernmodule & Offline-Proof (Status: 🟡 In Progress)
11. [x] **CRM:** Kontakte/Projekte/Suche (Basis vorhanden).
12. [ ] **Tasks:** Kanban Boards, SLA-Flags.
13. [ ] **Docs:** Upload, Tags, Volltext, Akten-Metapher.
14. [ ] **Workflows:** Event-Driven Rules, Confirm-Gates.
15. [ ] **Inbox Triage:** Mail/Dokument-Eingang → Task (High-ROI).
16. [ ] **Local AI:** Ollama-Integration (Policy-Gated).
17. [ ] **Offline Proof:** App läuft ohne Netz (außer Updates).

## 35% → 55%: Compliance-Baseline (EU) & Beta (Status: 🟡 In Progress)
18. [ ] **AuthZ Hardening:** Tests für unauthenticated/low-role Access.
19. [ ] **Session Hygiene:** Logout invalidiert, Idle-Timeout.
20. [ ] **GDPR-by-default:** Retention-Regeln, keine PII in Logs.
21. [ ] **AI-Transparenz:** Kennzeichnung synthetischer Inhalte (AI Act).
22. [ ] **Signaturen:** eIDAS-konformes Framing (Simple vs Advanced).
23. [x] **A11y Baseline:** EN 301 549 Mapping (`reports/REPORT_HARDENING_UX.md`).
24. [ ] **UX Gates:** Target Size (24px), Keyboard-Sanity.

## 55% → 70%: Release-Gates & Evidence Pack (Status: 🟢 Active Focus)
26. [x] **Release Gates:** Operationalisiert in `docs/RELEASE_GATES.md`.
27. [x] **Evidence Pack:** Einzige Wahrheit für Releases (`scripts/generate_evidence_pack.py`).
28. [ ] **Security Scan:** 0 High Vulnerabilities.
29. [x] **E2E Smoke:** Top-20 Flows definiert (`docs/qa/TOP_20_E2E_FLOWS.md`).
30. [ ] **Endurance:** 60-min Runner (Nightly).
31. [x] **PR-Checklist:** Evidence-Pflicht im Template (`.github/PULL_REQUEST_TEMPLATE.md`).

## 70% → 85%: RC-Enablement & Supply Chain (Status: 🔴 Blocked/Planned)
34. [ ] **macOS Dist:** Notary Pipeline (Codesign -> Notarize -> Staple). **(BLOCKED: Creds)**
35. [ ] **Windows Dist:** Signtool Pipeline. **(BLOCKED: Host)**
36. [ ] **SBOM:** CycloneDX Output pro Release.
37. [ ] **Provenance:** SLSA Build Provenance.
38. [x] **CRA Readiness:** Reporting Runbook (`docs/SECURITY_REPORTING_CRA.md`).

## 85% → 100%: Release Candidate (Strict Mode)
40. [ ] **NO-GO Regeln:** Keine P0 Bugs, 60-min Endurance Pass.
41. [ ] **Final Dist Check:** `spctl` / `signtool verify` PASS.
42. [ ] **E2E Coverage:** >95% Pass Rate für Core Flows.
43. [ ] **UX Automation:** Loading/Error/Keyboard automatisiert geprüft.
44. [ ] **Network Lockdown:** "No external requests" Gate enforced.

## 100% → 110%: Vision & Moat (Business OS)
A) **Time-to-Value:** Onboarding Wizard + Branchen-Templates.
B) **AI-Assistenz:** "Conversation as Shortcut" (mit Audit-Log).
C) **Vertical Kits:** Spezial-Workflows (Aufmaß, Abnahme) für Handwerk.
D) **Compliance-Sales:** EN 301 549 & GDPR als Verkaufsargument (mit Evidence).
E) **CRA Ops:** 24h/72h Reporting-Prozesse etabliert.

---

## Die Operative Checkliste (Release Captain)

1. [ ] Feature/Fix implementiert + Tests + Lint.
2. [ ] Security Suite PASS (AuthZ/Tenant).
3. [ ] E2E Smoke PASS + No External Requests.
4. [ ] Update/Rollback Proof PASS.
5. [ ] SBOM Scan PASS (0 High).
6. [ ] Endurance 60m PASS (für RC).
7. [ ] Distribution PASS (Notarized/Signed).
8. [ ] **Evidence Pack Generated** (`python3 scripts/generate_evidence_pack.py`).
9. [ ] **Release Decision:** GO / NO-GO based on Evidence.

---
*Dokumenten-Status: Living Document. Wird bei jedem Major-Milestone aktualisiert.*
