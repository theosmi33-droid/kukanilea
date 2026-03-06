# MIA-Orchestrator MVP (Skeleton)

## Überblick

Der MVP ergänzt einen deterministischen `ManagerAgent`, der ohne LLM-Entscheidungen kritische Aktionen auf Tool-Ebene routet.

Ablauf:
1. `parse_intent(message)` (regelbasiert)
2. `select(intent)` -> `(tool, action, requires_confirm, external_call)`
3. Confirm-Gate für write/critical Aktionen
4. Offline-First-Gate für externe Aktionen (`external_calls_enabled=False` default)
5. Event-Emission in `EventBus`
6. Audit-Log für jede Routing-Entscheidung

## Module

- `kukanilea/orchestrator/manager_agent.py`
  - `DeterministicToolRouter`
  - `ManagerAgent`
  - `EventBus`
  - `RouteDecision`, `RouteResult`

## Sicherheits-/Betriebsprinzipien

- **Deterministisch:** Kein LLM für Tool-Routing bei kritischen Aktionen.
- **Confirm-Gates:** Kritische Aktionen liefern `confirm_required`, bis ein valider Confirm-Token vorhanden ist.
- **Offline-First:** Externe Tool-Aktionen werden standardmäßig blockiert (`offline_blocked`).
- **Auditability:** Jede Route erzeugt EventBus-Event + Audit-Payload.

## Testplan (MVP)

- Routing korrekt auf Tool + Action.
- Confirm-Gate blockiert ohne explizite Bestätigung.
- Confirm-Gate erlaubt Route mit gültigem Token.
- Offline-First blockiert externe Calls ohne Feature-Flag.
- Contract-Endpunkte für Tool-Summary/Health sind global vorhanden.
