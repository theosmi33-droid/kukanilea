# KUKANILEA Systems — FIXED10 (Legacy UI)

## Start (Mac / zsh)
> Tipp: kopiere **jede Zeile einzeln**. Keine Klammern, keine Platzhalter.

### 1) Virtualenv + Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -r requirements.txt
```

### 2) UI starten (lokaler Agent-Orchestrator, kein externes LLM)
```bash
source .venv/bin/activate
./scripts/dev_run.sh
```

UI läuft auf: http://127.0.0.1:5051

## Dev-Login
- Username: `dev`
- Password: `dev`
- Tenant (Mandant): **KUKANILEA Dev** (fixed)

## Tool-Chat
- Floating Button unten rechts → Chat.
- Beispiele:
  - `suche rechnung gerd 24-10-2025`
- `öffne <token>` (öffnet den Datensatz im Browser)

## Projektstatus & Architektur
- Status: `PROJECT_STATUS.md`
- Architektur: `docs/ARCHITECTURE.md`

## GitHub Push (ohne Platzhalter-Zeilen)
```bash
git init
git add .
git commit -m "KUKANILEA: fixed10"
git branch -M main
git remote add origin https://github.com/theosmi33-droid/kukanilea.git
git push -u origin main
```
