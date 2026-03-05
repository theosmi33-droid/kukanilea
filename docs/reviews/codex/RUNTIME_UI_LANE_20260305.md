# Runtime UI Lane – Shell Stability (2026-03-05)

## Root Cause
- Der E2E-Uploadfluss war fragil, weil der Test den Upload aus dem Dashboard-Kontext mit altem Button-Selektor geprüft hat, statt die dedizierte `/upload`-Seite mit stabilem `input[name="file"]`-Pfad zu nutzen.
- Der `POST /upload`-Endpoint gab bislang immer JSON zurück. Bei Full-Page-Submit (ohne JS) oder HTMX-Navigation fehlte damit ein konsistenter Redirect-Pfad.
- Sidebar-Navigation konnte in HTMX-Boost-Kontexten in Partial-Load/Skeleton-ähnlichen Zuständen landen.

## Before
- Upload-Button/Selektor war nicht konsistent für E2E.
- `POST /upload` war API-only (JSON), kein sauberer Fallback für Full-Page.
- Sidebar war nicht explizit gegen HTMX-Boost abgesichert.

## After
- Upload-Seite nutzt klaren Primär-CTA (`#btn-upload`) und sendet bei Fetch explizit `Accept: application/json`.
- `POST /upload` unterscheidet jetzt JSON-, HTMX- und Full-Page-Requests:
  - JSON → strukturierte API-Antwort,
  - HTMX → `HX-Redirect`,
  - Full-Page → klassischer Redirect auf Review/Upload.
- Sidebar setzt `hx-boost="false"` für deterministische Full-Page-Navigation.
- E2E/UX-Tests decken Upload-Input-Präsenz und Sidebar-Boost-Verhalten explizit ab.
