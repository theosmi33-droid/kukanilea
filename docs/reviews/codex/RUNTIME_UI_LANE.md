# RUNTIME_UI Lane Report

## Overlap preflight
- `gh` CLI ist in der Laufzeitumgebung nicht verfügbar (`command not found`).
- GitHub API Fallback (`curl https://api.github.com/repos/theosmi33-droid/kukanilea/pulls?...`) lieferte `403 Forbidden`.
- Ergebnis: Kein belastbarer Overlap-Check auf offene PR-Dateien möglich (superseded risk konnte technisch nicht verifiziert werden).

## Umsetzung
- Sidebar-Navigation auf HTMX-Boost mit Full-Page-Fallback stabilisiert.
- `#main-content` als gezieltes HTMX-Target mit URL-Push/Historie konfiguriert.
- Bei HTMX-Response-Fehlern erfolgt harter Fallback auf `window.location`.
- E2E-Navigationstest robust gegen Umgebungen ohne Playwright-Browser ausführbar gemacht.
- Upload-Workflow-E2E an aktuellen Button-Text angepasst.

## Hinweise
- In dieser Container-Umgebung fehlen benötigte Runtime-Abhängigkeiten (Flask/Playwright-Browser), daher laufen Lane-Tests als Skip bzw. mit Infrastrukturwarnung.
