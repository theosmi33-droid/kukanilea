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
```

## Healthcheck
```bash
curl http://127.0.0.1:11434/api/tags
```

In der App:
- `GET /api/ai/status` pruefen
- Chat ueber `/chat` oder Widget unten rechts nutzen

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
