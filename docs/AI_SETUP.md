# Lokale KI mit Ollama (Phase 1.3)

## Ziel
KUKANILEA nutzt lokale LLM-Inferenz ueber Ollama (`localhost`) ohne Cloud-Abhaengigkeit.

## Voraussetzungen
- Ollama installiert
- Mindestens ein lokales Modell vorhanden (z. B. `llama3.1:8b`)

## Installation
```bash
ollama serve
ollama pull llama3.1:8b
```

## Konfiguration
Umgebungsvariablen:
```bash
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_MODEL="llama3.2:3b"
export KUKANILEA_OLLAMA_MODEL_FALLBACKS="llama3.1:8b,qwen2.5:3b"
export OLLAMA_TIMEOUT="300"
export KUKANILEA_AI_BOOTSTRAP_ON_FIRST_RUN="1"
export KUKANILEA_AI_BOOTSTRAP_PULL_MODELS="1"
export KUKANILEA_AI_BOOTSTRAP_USE_MODELPACK="1"
export KUKANILEA_AI_BOOTSTRAP_MODELPACK_FILE="$HOME/Library/Application Support/KUKANILEA/modelpacks/ollama-modelpack.tar.gz"
```

Beim ersten Start zieht KUKANILEA automatisch das Primaermodell + Fallback-Modelle
und schreibt den Status nach:
`~/Library/Application Support/KUKANILEA/ai_bootstrap_state.json`

## Offline-Modelpack (optional, empfohlen fuer Erstinstallation ohne Internet)

Auf einem vorbereiteten Build-/Admin-System:
```bash
python scripts/ai_modelpack_export.py --out "$HOME/Downloads/kukanilea-ollama-modelpack.tar.gz"
```

Auf Zielsystem importieren:
```bash
python scripts/ai_modelpack_import.py --pack "$HOME/Downloads/kukanilea-ollama-modelpack.tar.gz"
```

Oder direkt aus der App:
- `POST /api/ai/modelpack/export`
- `POST /api/ai/modelpack/import`

## Healthcheck
```bash
curl http://127.0.0.1:11434/api/tags
```

In der App:
- `GET /api/ai/status` pruefen
- Chat ueber `/chat` oder Widget unten rechts nutzen
- Optional fuer persoenliche Assistenz:
  - `POST /api/ai/personal-memory` mit `{"note":"..."}` speichert Notizen pro Nutzer lokal.
  - Chat-Kurzbefehl: `Merke dir: ...`

## Fail-Closed Verhalten
- Wenn Ollama nicht erreichbar ist, bleibt die App funktionsfaehig.
- `/api/ai/chat` liefert `status=ai_disabled`.
- Widget zeigt "KI offline" und deaktiviert Eingabe.

## Sicherheit
- Keine PII-Inhalte im Eventlog (`ai_conversation` enthält nur IDs/Counts).
- Tool-Use ist allowlisted (`search_contacts`, `search_documents`, `create_task`).
- Tenant-Isolation bleibt in allen Tool-Queries aktiv.

## Testmodus fuer CI / E2E
- Browser-E2E Tests nutzen keine echte Ollama-Instanz.
- Die KI-Schicht wird in `tests/e2e/test_ai_chat.py` und
  `tests/e2e/test_ai_smoke.py` gemockt.
- Damit bleiben Tests stabil und reproduzierbar ohne lokale Modell-Laufzeit.
