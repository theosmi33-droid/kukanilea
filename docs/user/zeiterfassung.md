# Zeiterfassung (Mitarbeiter)

## Überblick
- Eigene Zeiten in `Tag`, `Woche`, `Monat`, `Jahr`.
- Zwei Erfassungswege:
  - `Stoppuhr` (Start/Stop)
  - `Manueller Nachtrag` (von/bis)
- Optional: `Projekt` und `Task-Ref`.

## Stoppuhr nutzen
1. Projekt auswählen (optional).
2. Optional `Task-Ref` und Notiz setzen.
3. `Start` klicken.
4. Bei Ende `Stop` klicken.

Die laufende Zeit bleibt serverseitig als offener Eintrag (`end_at = NULL`) erhalten und wird beim Laden wieder angezeigt.

## Manueller Nachtrag
1. Im Block `Manueller Nachtrag` Start/Ende eintragen.
2. Optional Task-Ref und Notiz ergänzen.
3. `Nachtrag speichern`.

## Korrekturen (GoBD)
- Einträge werden **nicht gelöscht**.
- Korrektur erfolgt über `Storno` mit optionalem Grund.
- Stornierte Einträge bleiben auditierbar erhalten.

## Offline-First
- Bei Verbindungsproblemen werden Start/Stop/Nachtrag/Storno in einer lokalen Queue gespeichert.
- Nach Wiederverbindung werden Aktionen automatisch synchronisiert.

## Export
- CSV-Export enthält u. a.:
  - `user`
  - `project_name` / `task_ref`
  - `start_at` / `end_at`
  - `duration_seconds`
  - `is_cancelled`
