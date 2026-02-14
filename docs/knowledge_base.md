# Knowledge Base v1 (FTS5, Offline-First)

## Ziel
Knowledge Base v1 liefert eine lokale, tenant-getrennte Wissensablage mit SQLite FTS5-Suche. Keine Embeddings, keine externen Dienste.

## Tabellen
- `knowledge_chunks`: Source of truth für redigierte Inhalte.
- `knowledge_source_policies`: Tenant-Policies für erlaubte Quellen.
- `knowledge_fts`: FTS5-Index (external content auf `knowledge_chunks`).
- `knowledge_fts_fallback`: LIKE-Fallback falls FTS5 nicht verfügbar ist.

## Security/PII Defaults
- Default-Deny für PII-nahe Quellen (`lead`, `email`, `calendar`, `document`).
- `allow_customer_pii=0` blockiert diese Quellen.
- Redaction läuft standardmäßig auch für manuelle Notizen.
- Eventlog enthält niemals Notiz-Body/Titel/Tags.

## Suche v1
- Query wird tokenisiert und als AND-MATCH gebaut.
- Keine direkte Übergabe ungeprüfter MATCH-Operatoren.
- Ergebnis enthält Snippet (max 240 Zeichen), keine Volltextausgabe.

## FTS Rebuild (Admin/Dev)
Falls Inkonsistenzen auftreten:
- Core API: `knowledge_fts_rebuild(tenant_id=None)`
- FTS5: nutzt `INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')`
- Fallback: leert und befüllt `knowledge_fts_fallback` aus `knowledge_chunks`.

## UI/Endpoints
- HTML:
  - `/knowledge`
  - `/knowledge/notes`
  - `/knowledge/notes/new`
  - `/knowledge/settings`
- API:
  - `GET /api/knowledge/search`
  - `GET /api/knowledge/notes`
  - `POST /api/knowledge/notes`

## Read-only
Bei `READ_ONLY=true` sind alle Mutationen blockiert (Core + Route).
