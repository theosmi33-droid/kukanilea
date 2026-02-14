# 0013: Knowledge E-Mail Source v0 (Upload-only)

## Status
Accepted

## Entscheidung
- E-Mail-Ingestion nur über expliziten `.eml` Upload.
- Source ist standardmäßig deaktiviert (`allow_email=0`).
- Aktivierung erfordert zusätzlich `allow_customer_pii=1`.
- Speicherung nur redigierter Inhalte in `knowledge_chunks`.
- Keine Attachmentspeicherung; nur Metadaten-Flag.

## Begründung
- Security-first und offline-first bei minimaler Komplexität.
- Kein Netzwerkzugriff und keine Hintergrundprozesse.
- Dedup und Audit über tenant-sichere Tabellen + Eventlog ohne PII.

## Konsequenzen
- v0 priorisiert Sicherheit und Nachvollziehbarkeit vor Komfort.
- Spätere Integrationen (IMAP/OAuth) erfordern eigenes ADR und zusätzliche Härtung.
