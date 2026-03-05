# MARKET EVIDENCE (Handwerk) – Arbeitsversion

## Ziel
Dieses Dokument verbindet externe Marktbelege mit konkreten Produkt-Implikationen für KUKANILEA.

**Wichtig:** Die unten genannten Quellen sind als Research-Backlog zu verstehen und müssen durch das Team mit Originalzitaten, Datum und URL nachgezogen werden.

## Problemfelder im Handwerksalltag (priorisiert)
1. **Anfrage-Intake ist fragmentiert** (Telefon, Mail, Messenger, Fotos, Sprachnachrichten).
2. **Dokumentenfluss ist fehleranfällig** (Lieferscheine/Rechnungen verstreut, Fristen gehen verloren).
3. **Planung und Ausführung sind entkoppelt** (Aufgaben, Projekte, Kalender nicht konsistent).
4. **Zeiterfassung ist nicht baustellentauglich** (offline/vergessen/nachgetragen).
5. **Abrechnung verzögert den Cashflow** (Job fertig, Rechnung zu spät).
6. **Vertrauen/Compliance fehlen ohne belastbare Betriebsnachweise** (Backup/Restore/Lizenz/No-External-Requests).

## Evidence Pack (Quellen-Backlog)
> Status: **TODO (Research-Team)**

| Quelle | Themenfeld | Erwarteter Nachweis | KUKANILEA-Implikation |
|---|---|---|---|
| ZDH (Digitalisierung/Bürokratie/Fachkräfte) | Prozessdruck im Handwerk | Zeitverlust in Administration | Priorität auf Inbox→Task/Termin |
| KfW Research (Mittelstand, Digitalisierung) | Investitionshemmnisse | ROI-/Nutzenfokus, einfache Einführung | MVP auf 3–4 Killer-Flows begrenzen |
| Bitkom „Digital Office“ / IT-Security KMU | Medienbrüche, Sicherheitsanforderungen | Nutzen integrierter Workflows + Sicherheitsbarrieren | Confirm-Gates, lokale Verarbeitung |
| Destatis (Struktur/Arbeitszeit) | Größenklassen/Arbeitsrealität | typische Betriebsgröße und Kapazität | Defaults für kleine Teams, schnelle Flows |
| IHK/HWK-Leitfäden (GoBD-Praxis) | Aufbewahrung/Dokumentation | Pflichten und Revisionsanforderungen | Upload/OCR/Audit + Archivstrategie |
| BMF/Finanzverwaltung (GoBD/E-Rechnung) | Rechtlicher Rahmen | Fristen/Unveränderbarkeit/Nachvollziehbarkeit | Audit-Events, Exportpfade, Fristenautomatik |

## Priorisierte Killer-Flows (MVP)
### KF-1: Anfrage → Task/Projekt → Termin
- Einheitliches Intake-Envelope aus Mail/Messenger.
- KI darf nur Vorschläge machen, Ausführung nur nach Confirm.
- KPI: Zeit von Anfrage bis strukturierter Eintrag.

### KF-2: Dokument → Extraktion → Frist/Task
- OCR + Extraktion + Dead-Letter-Queue für unklare Dokumente.
- Zahlungsziel erzeugt Termin, Kosten werden Projekt zugeordnet.
- KPI: Auto-Klassifizierungsrate und Zeit bis Ablage.

### KF-3: Arbeit → Zeit → Export
- Timer direkt aus Aufgabe/Projekt, offline nutzbar.
- Tagesgleiche Erfassung und einfacher Export.
- KPI: Anteil tagesgleich erfasster Zeiten, Korrekturquote.

### KF-4: Ops-Vertrauen (Lizenz + Backup/Restore + Nachweis)
- Wiederholbarer Evidence-Drill mit PASS/WARN/FAIL.
- Restore-Verifikation als Pflicht.
- KPI: Backup-Erfolgsquote, Wiederherstellungszeit (RTO).

## Product-Policy (bindend für AI-Workflows)
- **Read-first:** ohne Bestätigung nur lesende Aktionen.
- **Write-after-confirm:** schreibende Aktionen nur mit expliziter Bestätigung.
- **Deny-by-default bei Unsicherheit.**
- **Mandantentrennung + 60-Tage-Retention** für AI-Memory.

## Nächste Umsetzungsschritte (2-Wochen-Sprint)
1. `summary + health` Contracts über alle Tools stabilisieren.
2. Killer-Flow KF-1 Ende-zu-Ende ausliefern.
3. KF-3 (Zeit→Export) mit baustellentauglichem Standardpfad schließen.
4. Evidence-Drill für Lizenz/Backup/Restore täglich belegbar machen.

## Checkliste für Research-Completion
- [ ] Für jede genannte Quelle: URL + Abrufdatum + Kernzitat eintragen.
- [ ] Für jede Kernfunktion: „Welches Problem wird gelöst?“ + Quellenbezug ergänzen.
- [ ] KPI-Baselines pro Pilotbetrieb dokumentieren.
