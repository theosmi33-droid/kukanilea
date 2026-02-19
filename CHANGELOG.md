# Changelog

## [Unreleased]

### Added
- Phase 5 packaging scripts under `scripts/build/` for obfuscation, macOS bundle and DMG creation.
- Separate `license_server/` prototype with `/api/v1/validate` and admin upsert endpoint.
- Notify-only update checker (`app/update_checker.py`) with optional Settings integration.
- Packaging and license-server documentation (`docs/packaging/*`, `LICENSE_SERVER.md`).

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
