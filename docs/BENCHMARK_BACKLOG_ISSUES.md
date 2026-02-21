# BENCHMARK_BACKLOG_ISSUES

Ziel: umsetzbare Issue-Stubs aus den Q1/2026-Benchmark-Nuggets, mit testbaren Akzeptanzkriterien und Release-Gate-Mapping.

## Issue 01
**Title:** E2E Smoke via Playwright for Top-20 flows (screenshots + request-id collection)
**Priority:** P0
**Rationale:** Lovable browser-testing pattern (real-user simulation with artifacts).
**Scope:** Automatisierte Kernflow-Tests fuer Login/CRM/Tasks/Docs/AI/Error-Pages.
**Acceptance criteria:**
- 20 Kernflows automatisiert abgedeckt.
- Jeder Fehlerfall liefert Screenshot + Console/Network Snippet + Request-ID.
- Lauf als CI-Job reproduzierbar.
**Testing plan:** CI-run + lokaler Re-run auf frischem Profil.
**Release gate mapping:** Beta (>=80% flow pass), RC (>=95%), Prod (kritische Flows 100%).

## Issue 02
**Title:** Workflow approvals + audit history + dashboard for overdue items
**Priority:** P0
**Rationale:** Haufe Freigabe-/Dashboard pattern.
**Scope:** Freigabestatus, Verlauf, Verantwortliche, Ueberfaelligkeitsansicht.
**Acceptance criteria:**
- Jeder Freigabeschritt mit Zeit/Actor/Status persistiert.
- Dashboard zeigt offene/ueberfaellige Freigaben.
- Evidence pack enthaelt Freigabehistorie.
**Testing plan:** API+UI integration tests fuer approve/reject/escalate.
**Release gate mapping:** Error-UX, Compliance/Privacy, Performance/Stability.

## Issue 03
**Title:** PWA companion for field capture (photo/signature/time) with offline queue + sync
**Priority:** P0
**Rationale:** Craftboxx + clockin (mobile/offline field capture).
**Scope:** Minimale Companion-PWA fuer Vor-Ort-Erfassung mit spaeterem Sync.
**Acceptance criteria:**
- Offline erfassbar: Foto, Zeit, Notiz, Status.
- Konfliktbehandlung sichtbar.
- Sync-Ereignisse auditierbar.
**Testing plan:** Offline/online toggle tests + conflict replay tests.
**Release gate mapping:** UX Kernflows, Performance/Stability, KI-Verfuegbarkeit (kein UI-Block bei Sync-Fails).

## Issue 04
**Title:** Integrations strategy: Lexware/sevdesk/DATEV export surfaces (docs + tests)
**Priority:** P0
**Rationale:** Craftboxx/clockin integration pressure in DACH handwerk.
**Scope:** Export contracts, sample payloads, contract tests, error codes.
**Acceptance criteria:**
- Versionierte Export-Schemas mit Beispielartefakten.
- Deterministische Fehlermeldungen inkl. Korrekturhinweis.
- Smoke-Export in staging testbar.
**Testing plan:** contract tests + fixture-based snapshot tests.
**Release gate mapping:** Distribution, Update/Rollback, Compliance/Privacy.

## Issue 05
**Title:** AI disclosure script + consent gates for voice/assistant use
**Priority:** P0
**Rationale:** AI transparency + telephony risk profile.
**Scope:** UI-Hinweis, API-Flag, Consent-Eventing fuer kritische Modi.
**Acceptance criteria:**
- Disclosure sichtbar in allen Assistant-Einstiegen.
- Consent-Status in Audit-Ereignis gespeichert.
- Voice/recording ohne Consent fail-closed.
**Testing plan:** UI assertion + API policy tests + negative tests.
**Release gate mapping:** Security, Compliance/Privacy, Error-UX.

## Issue 06
**Title:** Global Search + Command Palette (RBAC-aware, create-from-search)
**Priority:** P1
**Rationale:** Xentral Smart Search pattern.
**Scope:** Cmd/Ctrl+K Palette, berechtigungsgefilterte Treffer, quick-create actions.
**Acceptance criteria:**
- Keine Leaks auf nicht berechtigte Objekte.
- Treffer <300ms bei warm cache.
- Aktionen aus Suche auditiert.
**Testing plan:** RBAC negative tests + latency benchmark + UI smoke.
**Release gate mapping:** Security, UX Kernflows, Performance/Stability.

## Issue 07
**Title:** Deterministic intake for voice + inbox + chat into one queue
**Priority:** P1
**Rationale:** Fonio/Placetel/Starbuero intake convergence.
**Scope:** Einheitliches Intake-Schema fuer Kanaluebergreifendes Routing.
**Acceptance criteria:**
- Jeder Intake erzeugt standardisiertes Routingobjekt.
- Unknown-Faelle landen deterministisch in triage queue.
- UI bleibt benutzbar bei Provider-Ausfall.
**Testing plan:** end-to-end intake tests pro channel + fallback tests.
**Release gate mapping:** KI-Verfuegbarkeit, Error-UX, Security.

## Issue 08
**Title:** Call summary policy (minimal data mode)
**Priority:** P1
**Rationale:** Datenschutzanforderungen fuer Voice/Transkripte.
**Scope:** Konfigurierbarer "summary-only" Modus ohne Volltranskript-Speicherung.
**Acceptance criteria:**
- Default speichert nur strukturierte Felder.
- Volltranskript nur explizit aktiviert.
- Retention pro Datentyp konfigurierbar.
**Testing plan:** policy tests + data retention tests + eventlog key checks.
**Release gate mapping:** Compliance/Privacy, Security.

## Issue 09
**Title:** Signature level taxonomy (simple/advanced/qualified) in product UX
**Priority:** P1
**Rationale:** Paperless-style clarity avoids legal overclaim.
**Scope:** Klassifizierungstexte, Produktlabels, export disclaimers.
**Acceptance criteria:**
- UI unterscheidet Signaturlevel klar.
- Keine implizite QES-Behauptung ohne QES-Flow.
- Dokumentierte Entscheidungslogik je Use-Case.
**Testing plan:** copy review + workflow tests + legal checklist review.
**Release gate mapping:** Compliance/Privacy, Go/No-Go.

## Issue 10
**Title:** AI action-center with request-id linked traces
**Priority:** P1
**Rationale:** Moltbot-like orchestration requires operational traceability.
**Scope:** Unified trace view for AI decisions/tool calls/fallback hops.
**Acceptance criteria:**
- Jede Mutation hat request-id + decision trail.
- Confirm-gated actions eindeutig markiert.
- Exportable trace bundle fuer support.
**Testing plan:** tool policy tests + trace completeness checks.
**Release gate mapping:** Security, Error-UX, KI-Verfuegbarkeit.

## Issue 11
**Title:** Overdue SLA dashboard for tasks and approvals
**Priority:** P1
**Rationale:** Haufe dashboard and operations visibility benchmark.
**Scope:** SLA clocks, overdue counters, owner drill-down.
**Acceptance criteria:**
- Overdue-Berechnung tenant-scope korrekt.
- Drill-down auf Ursachen moeglich.
- No-Pii aggregated widgets.
**Testing plan:** aggregation tests + tenant isolation tests.
**Release gate mapping:** UX Kernflows, Performance/Stability.

## Issue 12
**Title:** Offline-first proof kit (demo script + failure drills)
**Priority:** P1
**Rationale:** Craftboxx/clockin offline claims set buyer expectations.
**Scope:** Repro script for offline operation and recovery.
**Acceptance criteria:**
- Definierter Testablauf fuer offline create/edit/sync.
- Recovery-Runbook mit Pass/Fail Nachweisen.
- Artefakte in release evidence bundle.
**Testing plan:** scripted smoke + manual validation checklist.
**Release gate mapping:** Distribution, Performance/Stability, Update/Rollback.

## Issue 13
**Title:** Compliance evidence bundle generator (docs + artifacts index)
**Priority:** P2
**Rationale:** Compliance as go-to-market proof (awork-style positioning).
**Scope:** Sammlung von Nachweisen pro Release-Gate in strukturiertem Format.
**Acceptance criteria:**
- Ein command erzeugt Evidence-Index.
- Jeder Gate-Bereich hat verlinkte Artefakte.
- Fehlende Evidenz wird als blocking markiert.
**Testing plan:** dry-run in CI, snapshot diff tests.
**Release gate mapping:** All gates.

## Issue 14
**Title:** Template-first automation catalog (recipes before builder)
**Priority:** P2
**Rationale:** Personio-style adoption via templates first.
**Scope:** Kuratierte Workflow-Vorlagen fuer handwerkliche Kernfaelle.
**Acceptance criteria:**
- Mindestens 10 produktive Templates.
- Install/enable/toggle/revert ohne manuelle JSON-Eingriffe.
- Template runs im activity log sichtbar.
**Testing plan:** workflow template integration tests + e2e activation checks.
**Release gate mapping:** UX Kernflows, Error-UX.
