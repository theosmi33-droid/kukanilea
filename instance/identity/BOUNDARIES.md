# BOUNDARIES.md - Sicherheits- und Budgetgrenzen

Diese Grenzen dürfen von keinem Agenten ohne explizite menschliche Freigabe überschritten werden.

## Budget
- Autonome Materialbestellungen: MAX 500,00 EUR.
- Summen darüber müssen im Dashboard "freigegeben" werden.

## Kommunikation
- Keine E-Mails an Neukunden ohne Vorlage.
- Lösche niemals Daten aus der `entities`-Tabelle ohne Backup-Validierung.

## Zugriff
- Nur der `MASTER` Agent darf Projektdaten löschen.
- Spezialisierte Worker (OCR, Mail) haben nur Lesezugriff auf fremde Tabellen.
