# In-Place Updates (Atomic Swap)

Stand: 2026-02-20

## Ziel

Updates ersetzen nur die App-Dateien. Benutzerdaten im Data-Directory bleiben unverändert.

## Trennung von App und Daten

- App-Verzeichnis: z. B. `/Applications/KUKANILEA.app` (macOS) oder Installationsordner unter Windows.
- Daten-Verzeichnis: `KUKANILEA_USER_DATA_ROOT` (standardmäßig OS-typisch unter Application Support/AppData).

Die Update-Logik arbeitet nur auf dem App-Verzeichnis.

## Ablauf

1. Release-Metadaten prüfen.
2. Installierbares ZIP-Asset auswählen.
3. ZIP herunterladen.
4. Optional SHA256 verifizieren.
5. App atomar ersetzen:
   - aktuelle App nach `<app>.backup` verschieben
   - neue App an Zielpfad verschieben
6. Bei Fehler: sofortiger Rollback aus Backup.

## DEV-Update Center

- Route: `/dev/update`
- Nur Rolle `DEV`
- Nur von localhost

Funktionen:
- `Check for Updates`
- `Install Update`
- `Rollback`

## Rollback

Ein Rollback nutzt das zuletzt angelegte Backup `<app>.backup`.
Wenn kein Backup vorhanden ist, wird der Rollback mit Fehler abgebrochen.

## Sicherheit

- Keine Datenmigration im Update-Schritt.
- Kein Überschreiben des Data-Directories.
- Fail-closed bei SHA256-Mismatch oder unvollständigem Paket.
