# FINAL EVIDENCE — 2026-03-04 13:25 UTC

## Scope
Worker C domains:
- excel-docs-visualizer
- einstellungen
- floating-widget-chatbot

Core evidence run in this repository path:
- `/workspace/kukanilea`

> Note: The requested absolute path `/Users/gensuminguyen/Kukanilea/kukanilea_production` is not present in this environment.

## A) Domain checkpoints

### 1) excel-docs-visualizer
- Branch: `codex/excel-docs-visualizer-checkpoint-20260304-1324`
- Command:
  - `python3 scripts/dev/check_domain_overlap.py --reiter excel-docs-visualizer --files app/routes/visualizer.py app/templates/visualizer.html`
- Result: `DOMAIN_OVERLAP_DETECTED`
- Outside allowlist:
  - `app/routes/visualizer.py`

### 2) einstellungen
- Branch: `codex/einstellungen-checkpoint-20260304-1324`
- Command:
  - `python3 scripts/dev/check_domain_overlap.py --reiter einstellungen --files docs/scopes/einstellungen.md`
- Result: `OK`

### 3) floating-widget-chatbot
- Branch: `codex/floating-widget-chatbot-checkpoint-20260304-1324`
- Commands:
  - `python3 scripts/dev/check_domain_overlap.py --reiter floating-widget-chatbot --files app/static/js/chatbot.js scripts/tests/test_chatbot_extended.py`
  - `PYENV_VERSION=3.12.12 python -m pytest -q scripts/tests/test_chatbot_extended.py`
- Overlap result: `DOMAIN_OVERLAP_DETECTED`
- Outside allowlist:
  - `scripts/tests/test_chatbot_extended.py`
- Test result: failed during collection (`ModuleNotFoundError: No module named 'flask'`).

## B) Core Evidence

### Branch
- `codex/final-evidence-20260304-1325`

### Gate commands
1. `scripts/ops/launch_evidence_gate.sh`
   - Failed: `unable to detect GitHub repository slug. Set REPO=owner/name.`
2. `REPO=theosmi33-droid/kukanilea scripts/ops/launch_evidence_gate.sh`
   - Produced artifact: `docs/reviews/codex/LAUNCH_EVIDENCE_RUN_20260304_132448.md`
   - Exit status non-zero with `fatal: Needed a single revision`
3. `./scripts/ops/healthcheck.sh`
   - Reached Python/DB steps
   - Failed in test step because pyenv expects `3.12.0` (not installed) and `pytest` not available for selected version

## Release recommendation
- **NO-GO** for merge/release in current environment.
- Required follow-ups:
  1. Fix domain allowlist overlaps for `excel-docs-visualizer` and `floating-widget-chatbot`.
  2. Install/align Python toolchain with `.python-version` or update environment.
  3. Install runtime test dependencies (at minimum `flask`) before rerunning tests.
  4. Ensure repository has a configured remote/valid revision for launch evidence gate.
