# Knowledge E-Mail Source v0

## Scope
E-Mail Source v0 erlaubt den manuellen Upload von `.eml`-Dateien als Knowledge-Quelle (`source_type=email`).

## Security Defaults
- Offline-only: kein IMAP, kein OAuth, keine Netzwerkanbindung.
- Policy-gated: `allow_email` + `allow_customer_pii` müssen aktiv sein.
- Default deny: E-Mail-Quelle ist standardmäßig deaktiviert.
- Keine Ausführung von Attachments oder fremdem Code.
- Attachments werden nicht gespeichert; nur `has_attachments` Flag.

## Pipeline
1. Upload `.eml` (max. Größe: konfigurierbar, default 2 MB).
2. Parse mit `email.parser.BytesParser` (stdlib).
3. Redaction auf Subject/Body (Email, Phone, lange Nummern, URLs).
4. Dedup via `content_sha256` je Tenant.
5. Speicherung in:
   - `knowledge_email_sources`
   - `knowledge_chunks` (`source_type=email`) für Suchindex
   - `knowledge_email_ingest_log` für PII-freie Diagnose
6. Eventlog `knowledge_email_ingested` ohne PII.

## PII-Regeln
- Kein Klartext von E-Mail-Adressen oder Telefonnummern im Eventlog.
- Kein Raw-Body im Eventlog.
- In Chunks nur redigierter Text.

## Known limitations v0
- Kein automatisches Mailbox-Ingest.
- Keine Attachment-Extraktion.
- Kein Customer-Linking über Klartext-Adresse.
