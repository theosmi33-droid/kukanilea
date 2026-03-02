# Visualizer Pipeline (Dev)

## Übersicht
Der Visualizer ist in drei Schichten aufgebaut:
1. `app/core/logic.py`: Payload-Builder und lokale Analyse
2. `app/web.py`: API-Endpunkte und Sicherheits-/Ablagefluss
3. `app/templates/visualizer.html`: UI-Rendering, Sort/Filter, Charts, Export-Trigger

## Datenfluss
1. `GET /api/visualizer/sources`
   - sammelt Quellen aus Pending, Recent Docs und Eingang
   - erlaubt nur Pfade innerhalb der bestehenden Allowlist
2. `GET /api/visualizer/render`
   - ruft `build_visualizer_payload(...)`
   - liefert je nach Typ:
     - `pdf`: Seitenbild + OCR/Meta-Layer
     - `sheet`: Grid + Heat-Layer
     - `image`: Bild + OCR-Zeilen
     - `text`: extrahierter Text + Meta
3. `POST /api/visualizer/summary`
   - ruft `summarize_visualizer_document(...)`
   - Injection-Safety: untrusted content sanitizen + harte Prompt-Grenzen
4. `POST /api/visualizer/note`
   - speichert Summary über `upsert_visualizer_note(...)`
5. `POST /api/visualizer/store-to-project`
   - legt über `ProjectManager.create_task(...)` eine Projektaufgabe an
6. `POST /api/visualizer/export-pdf`
   - erstellt lokal ein PDF mit Visual-Teil + Summary + optional Chart-Bild

## Sicherheit
- Source wird als serverseitig validierter Base64-Pfad verarbeitet.
- Zugriff nur für eingeloggte Nutzer.
- Nur allowlistete Pfade werden gelesen.
- Zusammenfassung behandelt Dokumentinhalt als untrusted data.

## Offline-Ansatz
- Kein CDN, keine Cloud-Libs im Visualizer-Pfad.
- Chart-Rendering via Canvas API lokal.
- Export via lokales PyMuPDF.

## Tests
- `tests/test_visualizer_routes.py`
  - Route Smoke + Summary/Note/Export
- `tests/test_visualizer_rendering.py`
  - Pipeline-Minimaltests (CSV/Text + Summary-Fallback)
