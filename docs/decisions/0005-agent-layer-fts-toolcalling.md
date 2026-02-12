# 0005: Agent Layer mit SQLite-FTS und Tool-Calling

## Status
Accepted

## Kontext
KUKANILEA braucht einen produktionsnahen Agent-Layer mit Retrieval, optionalem LLM und Tool-Calling, ohne schwere Zusatzabhängigkeiten und ohne Kernsysteme (Lizenz, Packaging, Serverstart) zu destabilisieren.

## Entscheidung
1. Retrieval nutzt ein separates SQLite-Index-DB unter `USER_DATA_ROOT/facts_index.sqlite3`.
2. Primärer Suchpfad ist FTS5; falls FTS5 zur Laufzeit fehlt, erfolgt deterministischer Fallback auf `LIKE`-Suche.
3. Der Orchestrator-Vertrag ist eingefroren und liefert exakt:
   - `text`
   - `facts`
   - `action`
4. Tool-Argumente werden mit `pydantic>=2.0` validiert.
5. Mutierende Tools sind strikt an `READ_ONLY` gebunden und werden bei aktivem Read-Only serverseitig blockiert.
6. Indexaktualisierung erfolgt queue-basiert über `rag_queue` mit begrenzter Verarbeitung pro Anfrage (`process_queue(limit=200)`). Kein Daemon.
7. Bei nicht verfügbarem Ollama degradiert das System auf Faktenantworten ohne Fehler-Throwing.

## Begründung
- Keine schweren Vektor-Stacks notwendig.
- SQLite ist bereits Teil des Betriebsmodells (local-first, offline-fähig).
- Laufzeit-Fallback erhöht Portabilität über unterschiedliche SQLite-Builds hinweg.
- Der eingefrorene Vertrag stabilisiert API/UI-Integration.
- Queue-Verarbeitung begrenzt Lastspitzen und hält Verhalten deterministisch.

## Konsequenzen
- Rankingqualität ist initial begrenzt auf BM25 bzw. LIKE-Matches.
- Toolset bleibt bewusst klein und strikt serverseitig kontrolliert.
- Erweiterungen (z. B. Embeddings) sind nur als optionales Plugin vorgesehen und dürfen den Antwortvertrag nicht brechen.

## Upgrade-Pfad
Eine optionale Embeddings-Erweiterung kann später hinter einem Feature-Flag wie `ENABLE_EMBEDDINGS` ergänzt werden. Dabei bleibt der Orchestrator-Output unverändert (`text`, `facts`, `action`).
