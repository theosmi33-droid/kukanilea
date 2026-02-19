# Packaging Build (macOS)

Stand: 2026-02-19

This guide builds a local macOS app bundle and DMG for KUKANILEA.
Build tools are release-time only and are not required at runtime.

## Prerequisites

- macOS host
- Python 3.11+
- Virtual environment with project dependencies
- Build tools installed locally:
  - `pyinstaller`
  - `pyarmor` (optional; if missing, source copy fallback is used)
  - `create-dmg` (optional; script falls back to `hdiutil`)

Install example:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller pyarmor
brew install create-dmg
```

## Build Steps

```bash
# 1) Optional code obfuscation (PyArmor or fallback copy)
scripts/build/obfuscate.sh

# 2) Build app bundle
scripts/build/bundle_macos.sh

# 3) Build DMG
scripts/build/dmg_macos.sh
```

Output artifacts:

- `dist/KUKANILEA.app`
- `dist/KUKANILEA-<version>.dmg`

## CI automation (Phase 5.1)

Installer builds are automated in GitHub Actions:

- `.github/workflows/build-macos.yml`
- `.github/workflows/build-windows.yml`

Behavior:

- `release.published`: builds run and upload installers to the GitHub Release.
- `workflow_dispatch`: builds run and publish artifacts in the workflow run.

Release outputs:

- macOS: `KUKANILEA-<version>.dmg`
- Windows: `KUKANILEA.exe`

## Compatibility wrappers

Legacy commands still work and forward to the new scripts:

- `scripts/build_mac.sh`
- `scripts/make_dmg.sh`

## Notes

- If `assets/icon.icns` exists, it is used automatically.
- If `create-dmg` is unavailable, `hdiutil` is used.
- For distribution outside trusted environments, add codesign/notarization.
- Windows build currently ships a standalone `.exe` (no NSIS/MSI wrapper yet).
