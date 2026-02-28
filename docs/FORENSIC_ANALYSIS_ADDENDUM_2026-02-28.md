# Addendum zur Forensischen Analyse (2026-02-28)

Dieses Addendum präzisiert die Laufzeit-Topologie im übergeordneten Projektordner `/Users/gensuminguyen/Kukanilea`.

## 1) Verifizierte Datenpfade

Es existieren zwei Laufmodi:

1. Default-Modus (ohne `KUKANILEA_USER_DATA_ROOT`):
- `/Users/gensuminguyen/Library/Application Support/KUKANILEA/auth.sqlite3`
- `/Users/gensuminguyen/Library/Application Support/KUKANILEA/core.sqlite3`

2. Ökosystem-Modus (mit `KUKANILEA_USER_DATA_ROOT=/Users/gensuminguyen/Kukanilea/data`):
- `/Users/gensuminguyen/Kukanilea/data/auth.sqlite3`
- `/Users/gensuminguyen/Kukanilea/data/core.sqlite3`
- zusätzlich vorhanden: `/Users/gensuminguyen/Kukanilea/data/Kukanilea_DB.sqlite3`

## 2) Präzisierung der kritischen Findings

### A) Memory-/Queue-Schema-Mismatch bleibt kritisch
- `agent_memory` und `api_outbound_queue` sind in `Kukanilea_DB.sqlite3` vorhanden.
- Die Runtime-Komponenten (`MemoryManager`, Dispatcher/API) greifen jedoch auf `Config.AUTH_DB`/`Config.CORE_DB` zu.
- In `auth.sqlite3`/`core.sqlite3` fehlen diese Tabellen in beiden Laufmodi.

Konsequenz:
- `store_memory()` schlägt in Runtime fehl (`no such table: agent_memory`).
- Queue-Statuspfad läuft in Fehler, sofern kein alternatives Schema aktiv eingespielt wurde.

### B) Zusätzlicher Befund im Ökosystem-Modus
Beim Start mit `KUKANILEA_USER_DATA_ROOT=/Users/gensuminguyen/Kukanilea/data` tritt auf:
- `Database Warmup Failed: foreign key mismatch - "deals" referencing "customers"`

Konsequenz:
- Schema-Drift/Inkompatibilität im produktionsnahen Datenbestand; separat als P0 behandeln.

## 3) Konkreter technischer Schluss

Das Hauptproblem ist nicht WAL oder Modellverfügbarkeit, sondern eine **DB-Routing-/Schema-Kohärenz**:
- Runtime-Module und Daten liegen auf unterschiedlichen historischen DB-Schemas.
- Ohne konsolidierte Migrationsstrategie bleibt Cognitive Core/Store-&-Forward instabil.

## 4) Sofortmaßnahmen (P0)

1. Festlegen einer einzigen „Source-of-Truth“-DB-Strategie (entweder Split `auth/core` oder monolithisch `Kukanilea_DB.sqlite3`).
2. DB-Routing in Code zentralisieren und überall gleich verwenden.
3. Idempotente Migrationen für die gewählte Strategie auf Boot erzwingen.
4. Warmup-Fehler `foreign key mismatch` mit Migrationsskript beheben und als Regression-Test absichern.

