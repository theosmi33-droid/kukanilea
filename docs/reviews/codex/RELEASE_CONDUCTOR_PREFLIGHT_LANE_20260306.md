# Release Conductor Preflight Lane — 2026-03-06

## Ziel
Diese Lane stabilisiert den **Pre-Flight-Ablauf** für mergebare PRs.

## Kontext
In mehreren Sessions wurden die gleichen manuellen Schritte wiederholt:

1. Offene PRs über `gh pr list` prüfen.
2. Laufende/letzte Main-Workflows über `gh run list` prüfen.
3. Lokalen Produktions-Clone auf uncommittete Änderungen prüfen.
4. Genau eine Lane aktiv halten.
5. Guard (`scripts/dev/pr_quality_guard.sh --ci`) vor Push ausführen.

Wenn `gh` oder der Produktionspfad fehlt, entstehen unklare Fehlermeldungen.

## Umsetzung
Es wurde ein dediziertes Hilfsskript ergänzt:

- `scripts/dev/release_conductor_preflight.sh`

Das Skript ist bewusst defensiv:

- erkennt fehlendes `gh` und markiert den Check als Warnung,
- erkennt fehlenden Produktionspfad und markiert den Check als Warnung,
- führt den PR-Guard trotzdem aus,
- führt (wenn vorhanden) einen fokussierten Testlauf aus,
- gibt eine standardisierte Summary aus.

## Standardisierte Summary-Felder
Die Ausgabe enthält exakt die Felder, die für den Lane-Report benötigt werden:

- `Lane`
- `Scope In`
- `Scope Out`
- `Guard-Result`
- `Test-Result`
- `PR-Link`

Zusätzlich wird ein kompakter Check-Status ausgegeben:

- `gh=<ok|warn>`
- `runs=<ok|warn>`
- `prod=<ok|warn>`

## Konfiguration über Umgebungsvariablen
Das Skript nutzt optionale Variablen:

- `RELEASE_REPO_SLUG`
- `PROD_REPO_PATH`
- `LANE`
- `PR_NUMBER`
- `SCOPE_IN`
- `SCOPE_OUT`

Damit kann der Ablauf ohne Codeänderung an andere Runner angepasst werden.

## Qualitätskriterien
Diese Lane richtet sich an bestehende Merge-Gates:

- MIN_SCOPE bleibt unverändert über `pr_quality_guard.sh`.
- MIN_TESTS bleibt unverändert über `pr_quality_guard.sh`.
- Lane-Overlap-Prüfung bleibt unverändert über `pr_quality_guard.sh`.

## Nicht-Ziele
Folgende Themen sind explizit außerhalb dieser Lane:

- keine Änderungen an Runtime/UI,
- keine Security-Policy-Änderungen,
- keine Änderung an Branch-Protection,
- keine Auto-Merge-Logik.

## Ausführung (Beispiel)

```bash
LANE=dev-ci \
PR_NUMBER=123 \
SCOPE_IN="CI guardrails" \
SCOPE_OUT="runtime, ui" \
bash scripts/dev/release_conductor_preflight.sh
```

## Ergebnis
Mit dem neuen Ablauf lässt sich die Session wiederholbar starten, auch wenn einzelne Infrastruktur-Tools lokal fehlen.
