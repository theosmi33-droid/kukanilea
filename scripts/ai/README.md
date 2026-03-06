# KUKANILEA AI CLI

## Ziel
Gemini-CLI und Codex lokal auf denselben Sovereign-11 Regeln ausrichten.

## Skripte
- `gemini_cli.py`: zentraler Gemini-Wrapper mit Alignment-Prompt und expliziter Approval-Mode-Wahl (`default`/`yolo`).
- `start_gemini_yolo.sh`: robuster YOLO-Starter mit Preflight (Auth, MCP, Referenz-Stack).
- `codex_auto_fix.sh <domain>`: ruff/black + Overlap-Quickcheck.
- `quick_start_cli.sh`: lokale CLI- und VS-Code-Hardening-Initialisierung.

## Beispiele
```bash
cd /Users/gensuminguyen/Kukanilea/kukanilea_production

# Gemini mit Domain-Kontext
.build_venv/bin/python scripts/ai/gemini_cli.py \
  --domain upload \
  --cwd /Users/gensuminguyen/Kukanilea/worktrees/upload \
  --approval-mode default \
  "Pruefe P0/P1/P2 und gib 3 sichere Commits aus."

# Gemini YOLO sicher starten (nur Checks)
bash scripts/ai/start_gemini_yolo.sh --check

# Gemini YOLO mit Headless-Test
bash scripts/ai/start_gemini_yolo.sh --headless-test

# Gemini YOLO interaktiv (mit festen Referenzen)
bash scripts/ai/start_gemini_yolo.sh

# Domain auto-fix
bash scripts/ai/codex_auto_fix.sh upload

# Fleet starten
bash scripts/orchestration/start_gemini_fleet.sh
```

## Approval-Mode (wichtig)
- Der Wrapper verlangt **explizit** einen Approval-Mode: `--approval-mode default|yolo` oder `GEMINI_APPROVAL_MODE`.
- Sichere Empfehlung fuer produktive/automatisierte Laeufe: `default`.
- `yolo` nur bewusst und sichtbar einsetzen (z.B. `GEMINI_FLEET_APPROVAL_MODE=yolo ...`).

