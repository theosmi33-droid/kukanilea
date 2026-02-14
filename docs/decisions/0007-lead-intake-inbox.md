# 0007 - Lead Intake Inbox

## Kontext
Für den Umsatzpfad "kein Lead geht verloren" wird ein einfacher, robuster Inbox-Flow benötigt.

## Entscheidung
- Additives Schema: `leads`, `call_logs`, `appointment_requests`
- Keine separate `lead_events` Tabelle
- Timeline basiert auf bestehendem Eventlog plus Fakten-Tabellen
- Eventlog `entity_id` bleibt INTEGER-kompatibel über deterministisches Mapping `entity_id_int(text_id)`

## Begründung
- Kein Doppel-Truth zwischen Domain-Events und Spezial-Tabelle
- Core-Freeze bleibt erhalten (`events.entity_id` unverändert)
- Mapping via SHA-256 (erste 8 Bytes) ist deterministisch und für erwartete Datenmengen praktisch kollisionsfrei

## Datenschutz
Eventlog-Payloads enthalten keine PII-Freitexte. Kontaktdaten und Nachrichten bleiben in Domain-Tabellen.
