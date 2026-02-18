# Market Research Workspace

Stand: 2026-02-18

Dieses Verzeichnis operationalisiert den integrierten Markt- und Produktplan fuer KUKANILEA.

## Inhalte
- `competitor_profile_template.md`: Standardstruktur fuer Einzelanalysen
- `competitor_matrix.csv`: Vergleichsmatrix ueber alle Ziel-Wettbewerber
- `weekly_research_plan.md`: 3-Wochen-Ausfuehrungsplan
- `profiles/`: eine Datei pro Wettbewerber

## Arbeitsregeln
- Jeder Claim braucht eine Quelle (URL + Datum)
- Preise, Compliance und Feature-Claims als Snapshot markieren
- Bei Unsicherheit `unverified` statt Behauptung

## Tooling
- Validierung der Matrix:

```bash
python -m app.devtools.market_research --matrix docs/market_research/competitor_matrix.csv --json
```

