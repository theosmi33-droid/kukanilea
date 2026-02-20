# AI Router

## Zweck

Der Router kapselt Provider-Auswahl, Health-Checks und Failover für KI-Anfragen.

Implementierung: `/Users/gensuminguyen/Tophandwerk/kukanilea-git/app/ai/provider_router.py`

## Ablauf

1. Lade Provider-Konfiguration (`KUKANILEA_AI_PROVIDERS_JSON` oder `KUKANILEA_AI_PROVIDER_ORDER`)
2. Erzeuge Provider-Clients
3. Prüfe Verfügbarkeit (Health-Check, TTL-cached)
4. Wähle den ersten gesunden Provider nach Priorität
5. Bei Fehler: nächster Provider

## Öffentliche API

- `provider_order_from_env()`
- `provider_specs_from_env()`
- `create_clients_from_specs()`
- `create_router_from_env()`
- `is_any_provider_available()`
- `provider_health_snapshot()`
- `chat_with_fallback(messages=..., tools=..., model=..., timeout_s=...)`

## Fehlerverhalten

- Kein Provider konfiguriert/gesund: `error_code=no_provider_available`
- Provider schlägt bei Request fehl: Router markiert ihn temporär ungesund und versucht den nächsten.
- Orchestrator bleibt fail-closed und liefert `ai_disabled`, wenn keine verwertbare Antwort verfügbar ist.

## API-Status Endpoint

`GET /api/ai/status` enthält:

- `provider_order`
- `provider_specs`
- `provider_health`
- `any_provider_available`
- `available`/`models` (Ollama-spezifische Legacy-Felder)
