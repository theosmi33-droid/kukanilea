# KUKANILEA Forensische Systemanalyse (v1.5 Cognitive Core)

Datum: 2026-02-28  
Workspace: `/Users/gensuminguyen/Kukanilea/kukanilea_production`  
Branch: `main`

## 1) Scope und Methode

Geprüft wurden die definierten Leitplanken und Fokusbereiche:
- Offline-First / lokale KI (Ollama)
- Zero-Bloat (keine schweren LLM-Frameworks)
- GoBD/Audit-Integrität
- Tenant-Isolation / tenant_id-Nutzung und Indizes
- Performance-SLA (<200ms Page-Loads) inkl. Boot-Overhead
- Agenten-Flotte, Cognitive Core, Tool-Runtime, API-Dispatcher
- Preflight: Python/venv, DB-WAL, Ollama-Modelle
- Validierung via `pytest tests/` inkl. Fokus-Tests

## 2) Preflight-Ergebnis

- Python in venv: `Python 3.12.0` (`./.venv/bin/python --version`) ✅
- Ollama erreichbar, Modelle vorhanden: `nomic-embed-text`, `qwen2.5:0.5b` (`ollama list`, `ollama show ...`) ✅
- Runtime-DBs (Config-Pfade) laufen mit WAL:
  - `AUTH_DB`: `/Users/gensuminguyen/Library/Application Support/KUKANILEA/auth.sqlite3` → `journal_mode=wal`
  - `CORE_DB`: `/Users/gensuminguyen/Library/Application Support/KUKANILEA/core.sqlite3` → `journal_mode=wal`
  - `audit_vault.sqlite3` → `journal_mode=wal` ✅
- Hinweis: `instance/Kukanilea_DB.sqlite3` ist leer (0 Byte) und **nicht** die aktive Runtime-DB.

## 3) Testergebnisse

- Fokus-Tests:
  - `tests/test_memory_system.py`
  - `tests/test_rag_pipeline.py`
  - `tests/test_lexoffice.py`
  - Ergebnis: `3 passed in 0.39s` ✅
- Gesamt-Suite:
  - `./.venv/bin/pytest -q tests/`
  - Ergebnis: `35 passed in 13.52s` ✅

## 4) Forensische Findings (priorisiert)

## KRITISCH

### F-001: Structured Logger ist syntaktisch defekt (GoBD-Logging nicht lauffähig)
- Evidenz:
  - Datei: `app/logging/structured_logger.py:26`
  - `python -m py_compile app/logging/structured_logger.py` → `SyntaxError: unterminated string literal`
- Impact:
  - Strukturierte Event-Logs sind in aktuellem Zustand nicht importierbar/ausführbar.
- Status: OFFEN

### F-002: Cognitive-Core Memory-Tabelle fehlt in Runtime-DB (Feature-Bruch)
- Evidenz:
  - `MemoryManager.store_memory(...)` gegen `Config.AUTH_DB` → `no such table: agent_memory`
  - Weder `auth.sqlite3` noch `core.sqlite3` enthalten `agent_memory`/`api_outbound_queue`
  - `app/core/migrations.py` definiert diese Tabellen, aber `run_migrations(...)` ist im Startup nicht verdrahtet
- Impact:
  - Semantisches Langzeitgedächtnis speichert nicht persistent.
- Status: OFFEN

### F-003: Store-&-Forward Queue nicht migriert, API-Endpoint läuft in 500
- Evidenz:
  - Datei: `app/api.py:103` nutzt `api_outbound_queue`
  - Runtime-Call mit Dev-Session auf `/api/outbound/status` → `500`, Fehler `no such table: api_outbound_queue`
- Impact:
  - Lexoffice-Queue-Monitoring und Outbound-Robustheit funktional gebrochen.
- Status: OFFEN

## HOCH

### F-004: RAG-SYNC wirft Laufzeitfehler bei Keyword-Fallback
- Evidenz:
  - Benchmark-Run loggt: `RAG-SYNC: Fact extraction failed: cannot access local variable 'Counter'...`
  - Ursache: `app/core/rag_sync.py:88` (`Counter`-Import im falschen Scope)
- Impact:
  - Intelligence-Sync degradiert, potenziell unvollständiges Gedächtnis-Update.
- Status: OFFEN

### F-005: Offline-First/No-Cloud verletzt durch optionale externe KI-Route (DeepL)
- Evidenz:
  - Datei: `app/plugins/mail.py:18` (`RewriteMode` enthält `deepl_api`)
  - Datei: `app/plugins/mail.py:60` (`https://api-free.deepl.com/v2/translate`)
- Impact:
  - Externer KI/Sprachdienst im Codepfad vorhanden; kollidiert mit „keine externen Cloud-APIs für KI-Funktionen“.
- Status: OFFEN (Policy-Entscheidung nötig: entfernen oder explizit opt-in + legal disclosure)

### F-006: Externes Frontend-CDN im UI-Template
- Evidenz:
  - Datei: `app/web.py:517` lädt `https://cdn.tailwindcss.com`
- Impact:
  - Verletzt lokale Asset-Strategie; abhängig von Internet und CSP-Policy.
- Status: OFFEN

### F-007: Audit-Zeitstempel in Core-Logik nicht UTC-normalisiert
- Evidenz:
  - Datei: `app/core/logic.py:212` nutzt `datetime.now().isoformat(...)` (naiv/lokal)
- Impact:
  - GoBD-Nachvollziehbarkeit leidet (uneinheitliche Zeitzone in Audit-Pfaden).
- Status: OFFEN

## MITTEL

### F-008: Dispatcher-Thread startet pro `create_app()`-Aufruf erneut
- Evidenz:
  - Datei: `app/__init__.py:66` startet `start_dispatcher_daemon(...)` unguarded
  - Mehrfache `create_app()`-Aufrufe erzeugen mehrfach „API Dispatcher Daemon started“
- Impact:
  - Potenziell unnötige Nebenläufigkeit in Tests/Reload-Szenarien.
- Status: OFFEN

### F-009: Sicherheitsheader/CSP inkonsistent zur Zielhärtung
- Evidenz:
  - Datei: `app/__init__.py:153` enthält `script-src 'unsafe-inline' 'unsafe-eval'`
- Impact:
  - Erhöhte XSS-Risikooberfläche; widerspricht strikter Sicherheitsbaseline.
- Status: OFFEN

### F-010: Fallback-`SECRET_KEY` hardcoded
- Evidenz:
  - Datei: `app/config.py:24` (`kukanilea-dev-secret-change-me`)
- Impact:
  - Risiko bei Fehlkonfiguration in produktionsnahen Umgebungen.
- Status: OFFEN

## 5) Leitplanken-Status

- Offline-First (KI): **TEILWEISE**
  - Positiv: Kern-LLM/Embeddings laufen über lokale Ollama-Endpunkte (`app/agents/llm.py`, `app/ai/embeddings.py`).
  - Negativ: DeepL-API-Pfad vorhanden (`app/plugins/mail.py`).
- Zero-Bloat: **ERFÜLLT**
  - Keine `langchain`/`llamaindex`-Einbindung in `app/`, `tests/`, `requirements*`, `pyproject.toml`.
- GoBD/Audit: **TEILWEISE**
  - Positiv: AuditVault mit Hash-Chain und Immutable-Triggern (`app/core/audit.py`).
  - Negativ: Defekter structured logger + nicht-UTC `_now_iso` in Core-Logik.
- Tenant-Isolation: **TEILWEISE**
  - Positiv: tenant_id-Spalten + zentrale Tenant-Indizes in Core-DB vorhanden.
  - Negativ: einzelne RAG-Abfragen ohne Tenant-Filter (`app/core/rag_sync.py:77` auf `vocab_index`).
- Performance-SLA: **TEILWEISE ERFÜLLT**
  - Page-Load (Testclient): `/login` ~3.63ms, `/api/health` ~3.72ms (<200ms) ✅
  - Cold Boot: ~0.53s (`create_app()`), Benchmark-CLI meldet `boot_time_ms: 1373` (kalt, inkl. Boot-Sequence).

## 6) Architektur-Fokus: Kurzbewertung

- Agenten-Flotte (`app/agents/`):
  - Orchestrator + Policy/Tool-Allowlist solide strukturiert; Observer mit Veto/Retry vorhanden.
- Cognitive Core (`app/core/rag_sync.py`, `app/agents/memory_store.py`):
  - Konzept korrekt (Chunking + Embeddings + MemoryManager), aber Runtime durch fehlende Tabellen/Migrationsverdrahtung aktuell funktional eingeschränkt.
- Tool-Runtime (`app/tools/registry.py`, `app/core/tool_loader.py`):
  - Dynamisches Laden/Registrieren ist vorhanden; fehlende Queue-Migration blockiert Lexoffice-Store-&-Forward-End-to-End.
- Resilienz (`app/services/api_dispatcher.py`):
  - Retry/Status-Handling implementiert; hängt derzeit an fehlender Queue-Tabelle.

## 7) Phase C (Rechtliches & Launch-Readiness) – nächste Schritte

1. **P0 Stabilität/Integrität zuerst schließen**
   - Structured logger reparieren.
   - `run_migrations(...)` verlässlich in den Startup-Pfad integrieren (inkl. idempotenter Checks).
   - `agent_memory`/`api_outbound_queue` in Runtime-DB nachziehen und Smoke-Test automatisieren.

2. **Policy-Härtung „local-first ohne Cloud-KI“ explizit codieren**
   - `deepl_api`-Pfad entfernen oder per Default hard-off + dokumentierte Opt-in-Rechtsgrundlage.
   - Externe CDN-Abhängigkeit in `app/web.py` eliminieren (lokal gebundelte Assets).

3. **GoBD-Nachweis vereinheitlichen**
   - Alle Auditpfade auf UTC ISO-8601 umstellen.
   - Unveränderlichkeit für zentrale Audit-Tables technisch enforcebar machen (Trigger/Append-only-Schema, falls gefordert).

4. **Launch-Legal Paket laut Fahrplan schließen**
   - AGB, EULA, Datenschutzerklärung, Impressum, ggf. Cookie-Banner (falls Tracking).
   - Release-Gate: keine Public-Freigabe ohne diese Dokumente.

5. **Release-Evidence und RC-Gates**
   - Distribution weiterhin BLOCKED bis Signing-Preconditions erfüllt.
   - Endurance/Hardening-Nachweise als feste Gate-Artefakte führen.

## 8) Command-Evidence (ausgeführt)

- `./.venv/bin/python --version`
- `ollama list`
- `ollama show nomic-embed-text:latest`
- `ollama show qwen2.5:0.5b`
- `./.venv/bin/pytest -q tests/test_memory_system.py tests/test_rag_pipeline.py tests/test_lexoffice.py`
- `./.venv/bin/pytest -q tests/`
- `./.venv/bin/python -m py_compile app/logging/structured_logger.py`
- Laufzeitprüfungen via Python-Snippets auf `Config.AUTH_DB`/`Config.CORE_DB`, Journaling, Tabellenbestand, API-Endpoint-Verhalten
- `./.venv/bin/python kukanilea_app.py --benchmark`

