# Process Notes — Phase 3.1 (License Hardening)

Stand: 2026-02-19

Scope:
- Post-merge Hardening fuer Lizenz-Enforcement nach PR #93.
- Keine neuen Runtime-Dependencies.
- Deterministische Failure-Modes (fail-closed), CI-stabile Tests ohne Live-License-Server.

Changes:
- Lokaler License-Server-Stub fuer Tests hinzugefuegt.
- Offline/Grace/Revocation-Abdeckung mit Stub-Tests erweitert.
- Operatives Runbook fuer Lizenz-Enforcement hinzugefuegt.
- Privacy-Hinweis zur Hardware-ID klarer dokumentiert (pseudonymisiert, nicht anonym).
