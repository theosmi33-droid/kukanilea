# Visualizer (The Forensic Eye)

## Zweck
Der Visualizer macht Dokumente lokal lesbar und verständlich:
- Anzeige von PDF, Office (DOCX/PPTX/XLSX), Bildern und Textdateien
- Tabellen mit einfacher Sortierung und Filter
- Lokale KI-Zusammenfassung mit Quellenhinweis
- Lokale Diagrammerzeugung aus Tabellen
- Export der visualisierten Ansicht als PDF
- Ablage als Projekt-Task über bestehende Projekt-Schnittstelle

## Nutzung
1. Menü `Excel Visualizer` öffnen.
2. In der linken Liste ein Dokument auswählen.
3. Je nach Dokumenttyp nutzen:
   - `Zurück/Weiter` für PDF-Seiten
   - `+/-` für Zoom, `Fullscreen` für Vollbild
   - `OCR` / `Meta` / `Force OCR` für Layer-Steuerung
4. Für Tabellen:
   - Spaltenkopf klicken, um zu sortieren
   - Filterfeld verwenden, um Zeilen zu filtern
5. `Summary erstellen` klickt eine lokale Zusammenfassung.
6. Optional:
   - `Als Notiz speichern`
   - Diagrammtyp wählen + `Chart erzeugen`
   - Projekt wählen + `Im Projekt ablegen`
   - `Als PDF exportieren`

## Datenschutz / Offline
- Alle Schritte laufen lokal.
- Keine Cloud-Bibliothek erforderlich.
- Zusammenfassung nutzt nur lokales LLM (falls vorhanden), sonst lokalen Heuristik-Fallback.

## Performance-Hinweise
- Erstes Renderziel: unter 2 Sekunden.
- Folge-Renderings nutzen Cache und sind typischerweise schneller.
