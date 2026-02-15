# ADR 0019: Autonomy Phase 2b (Auto-Tagging, Tokens, Dedup)

## Status

Accepted

## Kontext

Phase 2a liefert Excludes, globale Tags und Dateinamen-Metadaten. Der naechste Schritt ist, diese Informationen automatisch und tenant-sicher auf Knowledge-Inhalte anzuwenden, ohne OCR/Netzwerk/Exec-Pfade hinzuzufuegen.

## Entscheidung

1. **Regelbasierte Auto-Tagging-Engine**
   - Neue Tabelle `auto_tagging_rules`.
   - Streng allowlisted Condition-/Action-DSL.
   - Regeln werden kanonisiert gespeichert und deterministisch nach Prioritaet ausgefuehrt.

2. **Tokens statt Freitext**
   - `doctype_token` und `correspondent_token` auf `source_files` (und `knowledge_chunks`).
   - Nur stark eingeschraenkte Tokenformate, keine Klartext-PII.

3. **Dedup vor Ingest**
   - Vergleich via `sha256` + `size_bytes`.
   - Bei Treffer wird Ingest uebersprungen und auf kanonische Datei verwiesen.

## Konsequenzen

- Weniger doppelte Ingests und stabilere Tagging-Ergebnisse.
- Bessere Such-/Filterbarkeit ueber sichere Tokens.
- Kein Core-Freeze-Bruch: nur additive, idempotente Schema-Aenderungen.

## Sicherheitsaspekte

- READ_ONLY blockiert alle Mutationen (Core + Route).
- Eventlog bleibt PII-frei (keine Pfade/Dateinamen/Inhalte).
- Keine neuen Dependencies, kein Netzwerk, keine Codeausfuehrung.

## Nicht Teil dieser ADR

- OCR oder Inhaltsklassifikation.
- Externe Connectoren (IMAP/CalDAV/Webhooks).
