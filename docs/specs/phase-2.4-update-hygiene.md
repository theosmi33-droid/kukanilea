# Phase 2.4: Update & Hygiene

## Ziel
Ein lokaler, rebase-only Update-Workflow, der deterministisch bleibt und Konfliktmarker im Repo verhindert.

## Scope
- Update-Skript für macOS (Shell + Finder-kompatibel).
- CI/Tests schlagen fehl, wenn Konfliktmarker vorhanden sind.
- Repo-Hygiene für lokale DB-Artefakte.

## Out of Scope
- Automatisches Merge-Handling oder Konfliktauflösung.
- Remote/Cloud-Updates oder Telemetrie.
- Änderungen an produktiven Workflows außerhalb des Update-Flows.

## Akzeptanzkriterien
- Ein frischer Clone kann per `scripts/update.sh` rebase-only aktualisiert werden.
- CI/Tests schlagen fehl, wenn `<<<<<<<`, `=======` oder `>>>>>>>` im Repo vorhanden sind.
- DB-WAL/SHM-Dateien in `instance/` werden nicht versioniert.

## Sicherheits- und DSGVO-Aspekte
- Update-Flow läuft lokal und offline-fähig, keine externen Datenübertragungen.
- Keine sensiblen Inhalte werden geloggt oder übertragen.

## Risiken
- Fehlende `origin`-Remote-Konfiguration führt zum Update-Abbruch (gewollt: kein stiller Fallback).
- Lokale uncommitted Änderungen können den Rebase behindern (mit Autostash minimiert).
