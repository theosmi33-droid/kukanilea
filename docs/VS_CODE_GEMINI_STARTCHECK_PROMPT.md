# VS Code Prompt: Startklar + Modell-Check (Gemini-only Workflow)

Kopiere diesen Prompt in Gemini Code Assist (VS Code) im Projektordner `/Users/gensuminguyen/Kukanilea/kukanilea_production`.

```text
Rolle
Du bist mein Principal Release/Runtime Engineer für KUKANILEA.
Arbeite nur im aktuellen Workspace und führe keine destruktiven Git-Operationen aus.

Ziel
Prüfe vollständig, ob das Projekt startklar ist und ob das Runtime-KI-Modell korrekt gesetzt ist (lokal Ollama, kein Remote-Fallback).

Pflichtschritte
1) Führe den Ready-Check aus:
   bash scripts/vscode_ready_check.sh
2) Wenn der Check fehlschlägt:
   - identifiziere exakte Ursache
   - behebe sie minimal-invasiv
   - führe den Check erneut aus
3) Prüfe danach zusätzlich:
   - pytest -q
   - gh auth status
4) Lies den aktiven Provider direkt aus Python:
   python - <<'PY'
from app.agents.llm import get_default_provider
p = get_default_provider()
print({'provider': p.name, 'model': getattr(p,'model',None), 'available': getattr(p,'available',None)})
PY

Erwartete Zielwerte
- provider == "ollama"
- KUKANILEA_REMOTE_LLM_ENABLED == "0"
- OLLAMA_ENABLED == "1"
- /health und /api/health erreichbar
- pytest grün

Ausgabeformat
- Abschnitt "Status"
- Abschnitt "Gefundene Probleme"
- Abschnitt "Fixes"
- Abschnitt "Finaler Go/No-Go"
- Abschnitt "Nächste 3 Schritte"

Regeln
- keine Änderungen außerhalb des Workspaces
- keine Secrets ausgeben
- bei Blockern konkret sagen, welche Voraussetzung fehlt
```

## Kurzbedienung in VS Code
- `Cmd+Shift+P` -> `Tasks: Run Task`
- Starte `KUKANILEA: Ready Check (Gemini + Runtime)`
- Für tägliche Routine danach: `KUKANILEA: Pytest (all)`
