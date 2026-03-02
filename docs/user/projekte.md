# Projekt Hub (Projekte)

Der Projekt Hub ist ein lokales Kanban-Board fuer Projektsteuerung, angelehnt an MeisterTask.

## Kernfunktionen
- Projekte und Boards anlegen
- Frei konfigurierbare Spalten
- Karten mit Titel, Beschreibung, Faelligkeit, Verantwortlichen
- Drag-and-drop zwischen Spalten
- Kommentare und Anhaenge (Upload-Handoff per Pfad/Link)
- Aktivitaetsverlauf pro Board

## Bedienung
1. Oeffne `Projekte` in der Sidebar.
2. Lege bei Bedarf ein neues Board an.
3. Erstelle Spalten und danach Karten.
4. Ziehe Karten per Drag-and-drop zwischen Spalten.
5. Trage beim Verschieben einen Grund ein. Dieser wird im Aktivitaetsverlauf und semantischen Gedaechtnis gespeichert.

## Karten-Details
Nach Klick auf eine Karte kannst du:
- Titel/Beschreibung/Faelligkeit/Verantwortliche aktualisieren
- Kommentare erfassen
- Anhaenge als Pfad/Link hinterlegen
- Task-Verknuepfung ausloesen (`Link Task`), wenn Task-Schnittstelle verfuegbar ist
- Timer starten (`Start Timer`), wenn Zeiterfassungsschnittstelle verfuegbar ist

## Offline-Verhalten
- Board-Nutzung ist lokal moeglich.
- Drag-and-drop reagiert sofort in der UI.
- Bei API-Fehler wird die Bewegung zurueckgesetzt.

## Hinweise
- Mandantentrennung erfolgt ueber `tenant_id`.
- Jede relevante Aenderung wird in Activity, Audit und `agent_memory` abgelegt.
