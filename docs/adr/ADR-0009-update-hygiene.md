# ADR-0009: Rebase-only Update & Conflict-Marker Guard

## Status
Accepted

## Kontext
Lokale Updates müssen rebase-only bleiben, um Merge-Commits und Konfliktmarker zu vermeiden. Konfliktmarker haben bereits zu SyntaxError geführt.

## Entscheidung
- Ein lokales Update-Skript führt `git pull --rebase --autostash` aus und startet die Standard-Checks.
- Ein Test bricht CI ab, wenn Konfliktmarker im Repo gefunden werden.
- Lokale DB-WAL/SHM-Artefakte in `instance/` werden ignoriert.

## Konsequenzen
- Updates sind deterministisch und rebase-only.
- Konflikte werden früh erkannt und blockieren die CI.
- Repo bleibt frei von transienten DB-Dateien.
