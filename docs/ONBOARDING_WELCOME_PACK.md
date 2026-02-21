# KUKANILEA – Onboarding Welcome Pack

**Stand:** Samstag, 21.02.2026

## 1) Zielbild
KUKANILEA ist ein **local-first, offline-first** Business OS für operative Kernprozesse (CRM, Tasks, Dokumente/Wissen, Workflows, KI-Assistenz). Sicherheits- und Betriebsprinzipien:
- Single-Tenant-Isolation serverseitig erzwungen
- RBAC mit deny-by-default
- Security-by-default (u. a. CSP, minimierte externe Abhängigkeiten)
- Native Nutzung auf macOS/Windows

## 2) Faktischer Projektstand
- Release-Tag: `v1.0.0-beta.2`
- Aktiver Fokus-PR: `#129` (lokaler Ollama-Modell-Fallback)
- Letzter gemeldeter Teststand: `549 passed, 1 skipped`
- Bereits integrierte Hauptbausteine: Tenant-Lock, In-Place-Update, Idle-Timeout, lokale Fonts/CSP, RBAC, Error-Shell, Provider-Router

## 3) Rolle des neuen Kollegen (Primärmission)
**Qualität, Risikoabsicherung, UX/Compliance-Readiness**.

Im Fokus:
- UX-Audit und Flow-Stabilität (keine Sackgassen)
- Compliance-/Legal-Readiness (Privacy, Drittanbieter, Distribution)
- Release-Readiness (Abnahme, Artefakte, Nachweise)

Nicht im Fokus:
- Feature-Coding als Standardaufgabe
- unstrukturierte Feedback-Sammlungen ohne Repro/Evidence

## 4) Arbeitsmodus mit Codex

### Ticket-Format (Pflicht)
- Kontext
- Repro-Schritte (deterministisch)
- Expected
- Actual
- Priorität (`P0/P1/P2`)
- Akzeptanzkriterien (testbar)
- Artefakte (Screenshots, Logs, Request-ID, Build/OS)

### Definition of Done (DoD)
- Verhalten korrekt inkl. Edge-Cases
- keine Security-Regression
- Tests/CI angepasst und grün
- kein neuer UX-Dead-End
- Doku/Release Notes aktualisiert, wenn Nutzerverhalten betroffen
- Rollout-/Fallback-Verhalten dokumentiert

## 5) 30-60-90 Plan (deliverable-orientiert)

### Tage 1–30: Verstehen & Audit
- Top-20 Kernflows dokumentiert (Pass/Fail)
- Top-10 Findings mit Severity + Evidence als Issues
- Compliance-Draft (Privacy/Lizenzen/Distribution) mit Ownern

### Tage 31–60: P0/P1 schließen & Regression
- P0-Findings in PRs/Tickets mit AK überführt und nachgetestet
- Cross-Platform-Smoke (macOS/Windows) dokumentiert
- RC-Readiness-Report mit offenen Risiken und Go/No-Go-Status

### Tage 61–90: Polish & Launch-Entscheidung
- P1-Backlog messbar reduziert
- Distribution-Readiness inklusive Support-Texte final
- Go/No-Go-Vorlage für nächste Release-Stufe

## 6) First Day Cheatsheet

### In 60 Minuten
- Produktziel und laufende Prioritäten lesen
- Hauptnavigation einmal vollständig durchlaufen
- Erste UX-/Error-Signale notieren

### In 2–3 Stunden
- Drei reproduzierbare Findings dokumentieren (inkl. Artefakte)
- Einen Fehlerfall gezielt provozieren und Recovery evaluieren
- Externe Requests/Assets als erste Compliance-Sichtung erfassen

### Bis Tagesende
- 3 strukturierte Issues (`P0/P1/P2`)
- Kurzreport: Top-3 Risiken, Top-3 Quick Wins, Doku-Lücken

## 7) Release-Governance
Der Release Captain nutzt `/Users/gensuminguyen/Tophandwerk/kukanilea-git/docs/RELEASE_GATES.md` als verbindliche Grundlage für Go/No-Go.

## 8) Referenzen
- OWASP Broken Access Control: <https://owasp.org/Top10/2025/A01_2025-Broken_Access_Control/>
- NIST AC-6 Least Privilege: <https://nist-sp-800-53-r5.bsafes.com/docs/3-1-access-control/ac-6-least-privilege/>
- Apple Platform Security (Code Signing): <https://support.apple.com/en-by/guide/security/sec3ad8e6e53/web>
- Apple Developer ID: <https://developer.apple.com/developer-id/>
- Microsoft Desktop App Certification / Authenticode: <https://learn.microsoft.com/en-us/windows/win32/win_cert/certification-requirements-for-windows-desktop-apps-v3-3>
- Microsoft SmartScreen FAQ: <https://feedback.smartscreen.microsoft.com/smartscreenfaq.aspx>
