# KUKANILEA Beta 1 (v1.0.0-beta.1)

## Highlights
- Lokale KI: Ollama-Orchestrator mit Chat-Widget.
- Workflow-Engine mit tenant-sicherer Tool-Integration.
- Read-only Enforcement bei Trial/Lizenzzustand inkl. Aktivierungspfad ueber `/license`.

## Installation (Source)
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python kukanilea_app.py
```

## License Enforcement (Hardening)
- Added: **License-Validation-Stub** fuer lokale Tests.
- Added: **Offline/Grace/Revocation** Test-Suite.
- Added: **CI-Guard gegen Live-License-URLs**.
- Docs: `docs/runbooks/LICENSE_ENFORCEMENT.md` und `docs/PROCESS_NOTES_PHASE3_1.md`.

## Known Limitations (Beta)
- Kein DMG/Signing in diesem Release (Source-first Beta).
- Ollama muss lokal laufen, damit KI-Funktionen aktiv sind.
- Beta-Support erfolgt best-effort ueber Issues/Discussions.
