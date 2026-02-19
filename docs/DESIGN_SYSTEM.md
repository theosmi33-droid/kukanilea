# KUKANILEA Design-System v1.0

Ziel ist eine konsistente, wartbare UI über alle Bereiche (CRM, Tasks, Knowledge, Postfach, Automation, Omni).

## Leitlinien
- Eine zentrale App-Shell in `/app/web.py` (`HTML_BASE`) steuert Layout und globale UI-Tokens.
- Wiederverwendbare Jinja-Macros in `/templates/components/` statt ad-hoc Klassenmischung.
- Keine neuen Frontend-Dependencies (Core-Freeze).
- Mobile-First: Navigation und Hauptaktionen müssen auch auf kleinen Displays erreichbar sein.

## Design Tokens
- `--bg`, `--bg-elev`, `--bg-panel`: Hintergründe
- `--border`: Standard-Border
- `--text`, `--muted`: Primär-/Sekundärtext
- `--accent-500`, `--accent-600`: Primäre Aktionsfarbe
- `--radius-lg`, `--radius-md`, `--radius-sm`: Radius-Skala

## Komponentenklassen
- `card`: Panel für Inhalte
- `btn`, `btn-primary`, `btn-outline`, `btn-danger`: Schaltflächen
- `input`, `label`: Formularfelder
- `alert`, `alert-error`, `alert-warn`, `alert-info`: Statusmeldungen
- `table-shell`, `table-head`, `table-row`: Tabellenoberflächen

## Jinja-Komponenten
- `components/button.html`
- `components/alert.html`
- `components/form.html`
- `components/page_header.html`

## Regeln
- Keine neuen Inline-Styles in refactorten Bereichen.
- Tabellen nutzen `table-shell/table-head/table-row` statt einzelner Inline-Borders.
- Warnhinweise nutzen bevorzugt `alert`-Komponenten.
