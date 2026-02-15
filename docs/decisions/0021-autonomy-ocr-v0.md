# ADR 0021: Autonomy OCR v0

## Status
Accepted

## Kontext
Autonomy verarbeitet lokale Quellen bereits offline-first. Fuer gescannte Bilddokumente fehlt ohne OCR jedoch ein durchsuchbarer Textpfad.

Gleichzeitig gelten harte Sicherheitsvorgaben:
- keine neuen Dependencies
- keine Netzwerkanbindung
- keine dynamische Codeausfuehrung
- keine PII im Eventlog

## Entscheidung
Wir fuehren OCR v0 als strikt policy-gated Erweiterung ein:
- neues Policy-Flag `allow_ocr` (Default deny)
- neues Job-Audit `autonomy_ocr_jobs`
- OCR nur fuer Bilddateien (`jpg/jpeg/png/tiff`)
- PDF-OCR in v0 ausgeschlossen
- Tesseract-Aufruf nur mit `subprocess.run` als Argumentliste (`shell=False`, Timeout)
- OCR-Text wird vor Speicherung immer redigiert
- Eventlog-Payloads enthalten nur IDs/Status/Metriken

## Warum kein PDF-OCR in v0
PDF-OCR ohne zusaetzliche Konverter/Wrapper fuehrt in der Praxis zu hoehere Betriebs- und Sicherheitskosten. Das widerspricht dem v0-Ziel: kleine, deterministische, dependency-freie Erweiterung.

## Folgen
Positiv:
- bessere lokale Suchbarkeit von Bildquellen
- klare Audit-Trail fuer OCR-Laufstatus
- weiterhin offline-first und Core-Freeze-konform

Einschraenkungen:
- keine OCR fuer PDFs in v0
- OCR laeuft best-effort im Scan-Lauf und kann die Scanzeit erhoehen
