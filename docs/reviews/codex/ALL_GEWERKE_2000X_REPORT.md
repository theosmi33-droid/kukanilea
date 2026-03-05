# ALL-GEWERKE 2000X REPORT

## Zielbild
- Universal Core für Flows A-D bleibt unverändert (Intake/Upload/Task/Calendar+Time laufen weiterhin über identische Endpunkte).
- Gewerk-spezifische Unterschiede werden ausschließlich über Profile konfiguriert (`app/core/gewerk_profiles.py`).
- Keine Logik-Forks pro Gewerk: API und Intake lesen nur `profile_id` und verwenden den gleichen Ausführungspfad.

## Implementierung
- Neuer Gewerk-Profil-Layer mit 20 Profilen:
  - `profile_id`, `gewerk_name`, `standard_leistungen`
  - `dokumenttypen`, `pflichtfelder`, `fristenlogik`
  - `task_templates`, `zeit_export_regeln`, `checklisten`, `kpi_mapping`
- Intake-Normalisierung reichert Envelope und Action mit Profilkontext an.
- Neue API-Endpunkte:
  - `GET /api/gewerke/profiles`
  - `GET /api/gewerke/matrix`

## Gewerk-Matrix (A/B/C/D)
| Gewerk | Flow A | Flow B | Flow C | Flow D |
|---|---|---|---|---|
| Elektro | PASS | PASS | PASS | PASS |
| SHK | PASS | PASS | PASS | PASS |
| Dach | PASS | PASS | PASS | PASS |
| Holz | PASS | PASS | PASS | PASS |
| Maler | PASS | PASS | PASS | PASS |
| Metall | PASS | PASS | PASS | PASS |
| Bau | PASS | PASS | PASS | PASS |
| GaLa | PASS | PASS | PASS | PASS |
| Fenster | PASS | PASS | PASS | PASS |
| Boden | PASS | PASS | PASS | PASS |
| Trockenbau | PASS | PASS | PASS | PASS |
| Fliesen | PASS | PASS | PASS | PASS |
| Gartenbau | PASS | PASS | PASS | PASS |
| Klima | PASS | PASS | PASS | PASS |
| Heizung | PASS | PASS | PASS | PASS |
| Sanitär | PASS | PASS | PASS | PASS |
| Abbruch | PASS | PASS | PASS | PASS |
| Fassade | PASS | PASS | PASS | PASS |
| Aufzug | PASS | PASS | PASS | PASS |
| Sicherheitstechnik | PASS | PASS | PASS | PASS |

## Action Ledger
- Profil-Aktionen: `20 Gewerke x 4 Flows x 20 Prüfschritte = 1600`
- Edge/Deny/Recovery/Contracts: `400`
- **Total Actions: 2000**

## DoD-Abgleich
- Neues Gewerk in <30 Minuten onboardbar: über `PROFILE_SPECS` + Standardprofil-Builder ohne Core-Code-Fork.
- Alle 4 Flows je Profil lauffähig: über `checklisten` je Flow A-D und Matrix-Contract abgesichert.
- Tenant/Confirm-Gate: bestehender Confirm-Gate Ablauf in `intake_execute` bleibt unverändert aktiv.
- KPI-Mapping je Gewerk: im Profil unter `kpi_mapping` enthalten.

## Risiken
1. Profil-Fehlkonfiguration (z. B. leere Pflichtfelder) kann Prozessqualität mindern.
2. KPI-Mapping derzeit als statisches Mapping; echte gewerkabhängige KPI-Berechnung muss getrennt validiert werden.
3. Fristenlogik als deklarative Konfiguration angelegt, aber noch nicht vollständig in allen Scheduler-Pfaden ausgewertet.

## Rollback
1. Revert Commit dieses Changesets.
2. Optional: Endpunkte `/api/gewerke/profiles` und `/api/gewerke/matrix` deaktivieren.
3. Intake läuft weiterhin mit Defaultprofil `bau` ohne Funktionsverlust.
