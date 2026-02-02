# KUKANILEA Systems — Local UI (Release v1)

## What this bundle contains
- `kukanilea_app.py` — main Flask UI (Upload/Review/Ablage/Tasks/Assistant/Local Chat/Mail Agent tab)
- `kukanilea_core_v3_fixed.py` — core logic (DB, ingest, OCR/extract, archive rules)
- `kukanilea_weather_plugin.py` — weather helper (for Local Chat tools)
- `requirements.txt` — minimal Python deps
- `scripts/start_ui.sh` — starts UI + installs deps + sets env vars
- `scripts/ollama_bootstrap.sh` — starts Ollama + pulls model

## Quick start (macOS)
1) (Optional) install Ollama
- `brew install ollama`
- Run once: `scripts/ollama_bootstrap.sh`

2) Start UI
- `scripts/start_ui.sh`
- Open: http://127.0.0.1:5051

## Notes
- If you see a `zsh: parse error near ')'`, you likely pasted numbered lines like `# 1)` *without* the leading `#` or your terminal replaced quotes.
  Use the scripts above instead of copy/paste.
- Tenant/mandant: configured via account/license inside the app. Dev tenant: `KUKANILEA Dev`.

## GitHub recommended layout
Put these in a repo root:
- `kukanilea_app.py`
- `kukanilea_core_v3_fixed.py`
- `kukanilea_weather_plugin.py`
- `requirements.txt`
- `scripts/`
