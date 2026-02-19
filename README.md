# KUKANILEA (local-first business OS)

KUKANILEA is a local, tenant-aware operations platform for CRM, tasks/kanban,
documents/knowledge, workflows, and local AI assistance.

## Getting started (3 commands)
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt && python kukanilea_app.py
```
Open: [http://127.0.0.1:5051](http://127.0.0.1:5051)

Default dev login:
- `admin` / `admin`

## Key docs
- Quickstart: `QUICKSTART.md`
- Onboarding: `ONBOARDING.md`
- Configuration: `docs/CONFIGURATION.md`
- AI setup (Ollama): `docs/AI_SETUP.md`
- Workflows: `docs/WORKFLOWS.md`
- Pilot runbook: `docs/runbooks/pilot_v1.md`

## Data location (macOS)
`~/Library/Application Support/KUKANILEA/`

## Local AI
For local AI chat, run Ollama and pull a model:
```bash
ollama serve
ollama pull llama3.1:8b
```

## Quality gates
```bash
python -m compileall -q .
ruff check .
ruff format . --check
pytest -q
python -m app.devtools.security_scan
python -m app.devtools.triage --ci --fail-on-warnings
python -m app.devtools.schema_audit --json > /dev/null
```
