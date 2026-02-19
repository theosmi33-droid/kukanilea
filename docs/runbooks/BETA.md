# Beta Runbook

Stand: 2026-02-19

## Ziel
- Beta-Test mit 50-100 Early Adopters.
- Fehler/UX-Probleme strukturiert erfassen, priorisieren, beheben.

## Setup in < 10 Minuten
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python kukanilea_app.py
```

Optional (KI):
```bash
ollama serve
ollama pull llama3.1:8b
```

## Wichtige Pfade
- Konfiguration: `docs/CONFIGURATION.md`
- KI-Setup: `docs/AI_SETUP.md`
- Workflows: `docs/runbooks/WORKFLOWS.md`
- License Ops: `docs/runbooks/LICENSE_ENFORCEMENT.md`

## Troubleshooting
- KI deaktiviert: `OLLAMA_BASE_URL` pruefen und Ollama starten.
- Read-only unerwartet: `/license` aufrufen und `LICENSE_REASON` pruefen.
- Mail deaktiviert: `EMAIL_ENCRYPTION_KEY` setzen (fail-closed Verhalten).

## Feedback-Flow
- Bugs als GitHub Issue mit `beta` + `bug`.
- Kritische Bugs mit `critical`.
- Keine PII in Tickets oder Attachments posten.
