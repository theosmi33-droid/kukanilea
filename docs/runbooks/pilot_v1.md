# KUKANILEA Pilot-Runbook v1.0

Stand: 2026-02-19

## 1. Ueberblick
- Zielgruppe: 3-5 Pilotkunden (KMU)
- Pilotdauer: 2-3 Wochen
- Fokus: CRM, Tasks/Kanban, Dokumente/OCR, Automation
- Erwarteter Aufwand pro Kunde: ca. 2 Stunden Setup + taegliche Nutzung

## 2. Zielgruppen und Rollen
- Pilotkunden:
  - Installation
  - Demo-Daten laden
  - Happy Path testen
  - Feedback melden
- Internes Team (Support/Dev):
  - Monitoring
  - Incident-Triage
  - Fix-/Workaround-Kommunikation

## 3. Voraussetzungen
- macOS 12+ (Intel oder Apple Silicon)
- Lokale Schreibrechte auf Benutzerdatenverzeichnis
- Optional fuer OCR: `tesseract` lokal installiert

Hinweis:
- Ohne Tesseract bleibt der Pilot lauffaehig; OCR-Teile werden nur eingeschraenkt.

## 4. Installation (Kunde)
1. Neueste DMG herunterladen: [Release Download](https://releases.kukanilea.com)
2. DMG oeffnen und App nach `/Applications` ziehen
3. App starten
4. Falls Gatekeeper warnt: App in Systemeinstellungen explizit erlauben

Platzhalter Screenshot:
- [Bild einfuegen: Installation / Drag-and-drop]

## 5. Demo-Daten laden
### Option A (bevorzugt): integrierter Seed
- In der App als DEV anmelden
- Einstellungen -> Tools -> `Load Demo Data`

### Option B: CLI
```bash
python scripts/seed_demo_data.py --tenant-name "DEMO AG"
```

Optional neu aufsetzen (idempotent mit Reset):
```bash
python scripts/seed_demo_data.py --tenant-name "DEMO AG" --force
```

Erwartung nach erfolgreichem Seed:
- 1 Demo-Tenant
- Login `demo / demo`
- 5 Kontakte
- 10 Dokumente
- 3 Tasks
- 1 Automation-Regel

## 6. Happy Path (Kunde)
- [ ] CRM: Kontaktliste oeffnen, Kontakt suchen, neuen Kontakt anlegen
- [ ] Tasks: Task anlegen und Statuswechsel testen
- [ ] Dokumente: Datei hochladen / Scan pruefen
- [ ] Automation: Regel ausfuehren und Log pruefen

Platzhalter Screenshots:
- [Bild einfuegen: CRM Kontaktliste]
- [Bild einfuegen: Kanban / Task Status]
- [Bild einfuegen: Dokument-Ansicht]
- [Bild einfuegen: Automation-Logs]

## 7. Feedback-Prozess
Siehe: `/Users/gensuminguyen/Tophandwerk/kukanilea-git/docs/pilot_feedback.md`

Kurzfassung:
- Taeglicher asynchroner Check-in
- Woechentliche Zusammenfassung
- NPS nach 2 Wochen
- Bugs zentral als GitHub Issues

Issue-Tracker (Platzhalter):
- [Pilot Issues](https://github.com/theosmi33-droid/kukanilea/issues)

## 8. Troubleshooting (Support)
| Problem | Ursache | Loesung |
|---|---|---|
| App startet nicht | Quarantaene/Signierung | `xattr -d com.apple.quarantine /Applications/KUKANILEA.app` |
| Seed stoppt | Rechte/DB-Pfad | Logs pruefen, `--force` nur fuer Demo-Tenant nutzen |
| OCR liefert nichts | Tesseract fehlt | `brew install tesseract` |
| Keine Dokumente nach Seed | Policy/Source-Config | Knowledge-Policy + Source-Scan-Konfig pruefen |

## 9. Incident-Plan
- Critical (Datenverlust, Tenant-Leak, Security):
  - Sofort eskalieren
  - Pilot ggf. pausieren
  - Incident in Ticketing dokumentieren
- Major (Feature blockiert):
  - Innerhalb 24h Workaround oder Fix
  - Transparente Kundenkommunikation
- Minor:
  - Sammeln, priorisieren, nach Pilot sprinten

## 10. Go/No-Go Entscheidung
Nach 2-3 Wochen wird pro Pilottenant ausgewertet:

| Kriterium | Ziel | Quelle | Messmethode |
|---|---|---|---|
| NPS | > 40 | NPS-Umfrage | nach 2 Wochen |
| Kritische Bugs | < 5 | GitHub Issues (`critical`) | taeglich |
| Nutzungsfrequenz | > 3x/Woche | `pilot_metrics.json` | woechentlich |
| Feature-Adoption | > 50% nutzen >=2 Kernfeatures | Support-Bundle + Review | Ende Pilot |

Entscheidung:
- Go: alle Kernziele erreicht
- No-Go: priorisierte Iteration mit klaren Blockern und neuer Pilotrunde
