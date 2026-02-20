# Changelog

## [Unreleased]

### Added
- Phase 5 packaging scripts under `scripts/build/` for obfuscation, macOS bundle and DMG creation.
- Separate `license_server/` prototype with `/api/v1/validate` and admin upsert endpoint.
- Notify-only update checker (`app/update_checker.py`) with optional Settings integration.
- Packaging and license-server documentation (`docs/packaging/*`, `LICENSE_SERVER.md`).

## [v1.0.0-beta.2] - 2026-02-20

### Added
- Single-tenant lock with server-enforced tenant context and DEV-only tenant metadata override.
- In-place update mechanism with atomic swap and rollback safeguards.
- Server-side idle timeout (default 60 minutes) plus absolute session cap.
- Self-hosted fonts and CSP enforcement to block external font origins.
- RBAC permissions manager in settings for role and permission administration.

### Changed
- UI shell defaults to light theme for first-run and fallback rendering.
- Route-level error responses now negotiate HTML for browser navigation and render inside the app shell.

### Fixed
- WebView/browser error flows no longer strand users on raw JSON blobs without navigation.
- Error pages now include in-shell actions (`Neu laden`, `Zurueck`, `Dashboard`) and request-id display.

### Security
- Fail-safe error handling with public-safe messages and request-id correlation.
- Continued deny-by-default enforcement for tenant isolation and protected routes.

## [v1.0.0-beta.1] - 2026-02-19

### Added
- Foundation: Design-System, Workflows, lokaler LLM/Ollama-Orchestrator, Chat-Widget.
- Phase 2: E2E-Smokes, QA-Dokumente, Performance-Skripte, Security-Checks.
- In-App Lizenzaktivierung (`/license`) mit Read-only-Aktivierungspfad.

### Changed
- CI stabilisiert (resiliente Dependency-Installation, getrennte smoke/e2e Jobs).
- Lizenzvalidierung mit Grace-Handling dokumentiert.

### Security
- Read-only Enforcement bleibt fail-closed bei Trial/Lizenz-Problemen.
- Secrets-Scanning und Schema-Audit als feste Gates.

### License Enforcement (Hardening)
- Added: **License-Validation-Stub** fuer deterministische Tests ohne Live-Server.
- Added: **Offline/Grace/Revocation** Testabdeckung.
- Added: **CI-Guard gegen Live-License-URLs** in CI-Umgebungen.
- Docs: `docs/runbooks/LICENSE_ENFORCEMENT.md` + `docs/PROCESS_NOTES_PHASE3_1.md`.
