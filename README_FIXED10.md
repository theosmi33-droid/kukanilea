# KUKANILEA Systems — FIXED10 (UI + Tool-Chat + Mail Tab)

## Start (Mac / zsh)
> Tipp: kopiere **jede Zeile einzeln**. Keine Klammern, keine Platzhalter.

### 1) Virtualenv + Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -r requirements.txt
```

### 2) Ollama (einmalig Model ziehen)
```bash
ollama pull llama3.1
```

### 3) UI starten (auto Ollama-Start aktiv)
```bash
source .venv/bin/activate
export OLLAMA_HOST="http://127.0.0.1:11434"
export KUKANILEA_OLLAMA_MODEL="llama3.1"
export KUKANILEA_AUTO_START_OLLAMA="1"
python3 kukanilea_upload_ui_fixed10.py
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
  - `open 1` (öffnet Treffer 1 im Browser)

## GitHub Push (ohne Platzhalter-Zeilen)
```bash
git init
git add .
git commit -m "KUKANILEA: fixed10"
git branch -M main
git remote add origin https://github.com/theosmi33-droid/kukanilea.git
git push -u origin main
```
