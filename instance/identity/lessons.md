# lessons.md - Der Lern-Log

Hier notiert das System gelernte Lektionen aus Korrekturen durch den Inhaber.

## Gelernt am 2026-02-23
- Lektion: Zement-Lieferungen von "Baustoff Union" werden immer auf das Projekt "Lager" gebucht, sofern kein Projektcode angegeben ist. (Korrektur durch Inhaber)
- Lektion: Rechnungen unter 10€ benötigen keinen Eskalations-Entwurf.
\n### Korrektur 2026-02-23 22:35:17\nKONTEXT: Aktion: generate_material_order, Args: {"quote_id": 100}\nNUTZER-FEEDBACK: VETO durch Observer: Procurement-Veto: Original-Angebot #100 nicht gefunden.\n---\n\n### Korrektur 2026-02-23 22:35:17\nKONTEXT: Aktion: verify_supplier_invoice, Args: {"order_id": "order_123", "ocr_text": "RECHNUNG M\u00fcller GmbH, Zement 105.00 EUR"}\nNUTZER-FEEDBACK: VETO durch Observer: Observer konnte LLM-Antwort nicht validieren.\n---\n\n### Korrektur 2026-02-23 22:35:17\nKONTEXT: Aktion: send_appointment_mail, Args: {"recipient": "kunde@example.local", "subject": "Terminbest\u00e4tigung: Montage Waschbecken", "body": "Guten Tag, Ihr Termin wurde f\u00fcr den 01.03.2026 um 08:00 Uhr gebucht.", "ical_path": "instance/calendar/Termin_20260301_0800.ics"}\nNUTZER-FEEDBACK: VETO durch Observer: Observer konnte LLM-Antwort nicht validieren.\n---\n