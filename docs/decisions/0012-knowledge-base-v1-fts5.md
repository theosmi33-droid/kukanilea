# 0012: Knowledge Base v1 mit SQLite FTS5

## Status
Accepted

## Kontext
Wir brauchen eine sichere, lokale Wissenssuche ohne zusätzliche schwere Abhängigkeiten oder Cloud-Kopplung.

## Entscheidung
- SQLite FTS5 als Primärsuche.
- Fallback auf LIKE, wenn FTS5 in der SQLite-Build-Variante fehlt.
- Tenant-isolierte Ablage in `knowledge_chunks`.
- Strikte Source-Policy pro Tenant (`knowledge_source_policies`).
- PII-default-deny für `lead/email/calendar/document`.
- Eventlog ohne Inhalts-PII (nur IDs/Flags/Metadaten).

## Begründung
- Offline-first und deterministic ohne neue Dependencies.
- Minimales Risiko: keine Netzwerk-Ingestion, keine Embeddings, keine Script-Engine.
- Vorbereitung auf spätere Verknüpfung mit Login/E-Mail/Kalender über explizite Opt-in-Policies.

## Konsequenzen
- v1 ist bewusst konservativ bei Quellenfreigabe.
- Redaction ist Standard.
- Rebuild-Pfad für FTS ist dokumentiert.

## Hinweise
SQLite JSON-Funktionen sind ab 3.38 typischerweise verfügbar, können aber Build-abhängig deaktiviert sein.
