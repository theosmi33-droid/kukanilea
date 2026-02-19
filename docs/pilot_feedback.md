# Pilot Feedback Prozess

Stand: 2026-02-19

## Ziel
Konsistentes, vergleichbares Feedback aus 3-5 Pilotkunden einsammeln und in messbare Produktentscheidungen ueberfuehren.

## Rollen
- Pilot-Betreuer (Owner): fuehrt Check-ins durch, pflegt Status
- Support: sammelt technische Probleme und reproduzierbare Schritte
- Dev: bewertet Fix-Aufwand und liefert ETA

## Ablauf
1. Taeglicher Check-in (asynchron)
- Kanal: E-Mail oder Teams
- Fragen:
  - Was hat heute funktioniert?
  - Was hat blockiert?
  - Gibt es Daten-/Sicherheitsbedenken?

2. Woechentlicher Sync (30 Minuten)
- Offene Blocker
- Nutzungsmuster je Kernfeature
- Priorisierung bis naechste Woche

3. NPS-Umfrage nach 2 Wochen
- Formular-Link (Platzhalter): [NPS Formular](https://forms.gle/replace-this-link)
- Frage: "Wie wahrscheinlich ist es, dass Sie KUKANILEA weiterempfehlen?" (0-10)

4. Bug-Tracking
- Issues in GitHub mit Labels:
  - `pilot`
  - `bug`
  - optional `critical`
- Issue-Link (Platzhalter): [GitHub Issues](https://github.com/theosmi33-droid/kukanilea/issues)

## Datenbasis fuer Go/No-Go
- `pilot_metrics.json` aus Support-Bundle
- NPS-Ergebnisse
- Anzahl/Schwere offener Bugs
- Qualitatives Kundenfeedback aus Check-ins

## Eskalationsregeln
- Security-Incident oder Tenant-Leak: sofortiges Escalation-Ping an Dev + Management
- Datenverlust: sofortiger Incident-Call und Stopp weiterer Produktivtests bis Ursachenanalyse
- Kritischer Betriebsfehler >24h: Pilot-Scope einschranken und Kunden aktiv informieren
