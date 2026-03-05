# PERF KPI Report — 2026-03-05

## Scope
Die Lane `perf-kpi` liefert ein dauerhaftes Performance-/Stabilitäts-Gate mit Benchmark-Harness, KPI-Artefakt, Schwellenwert-Policy, optionalem CI-Job und Regressionstests.

## Implementierte KPIs
- **app start time**: gemessen via `create_app()` Bootdauer in ms.
- **/dashboard TTFB**: gemessen via Flask-Testclient für `/dashboard` mit authentifizierter Session.
- **/api/* summary latency**: gemessen für `/api/aufgaben/summary`, `/api/projekte/summary`, `/api/kalender/summary`.

## Schwellwerte
| KPI | Warn | Fail |
| --- | ---: | ---: |
| app_start_time_ms | 1500 ms | 2500 ms |
| dashboard_ttfb_ms | 250 ms | 450 ms |
| api_summary_latency_ms | 180 ms | 320 ms |

Status-Logik:
- `pass`: p95 < warn
- `warn`: warn <= p95 < fail
- `fail`: p95 >= fail

## Aktuelle Messergebnisse
Quelle: `docs/status/perf_kpi_latest.json` und `docs/status/KPIS.md`.

- Overall Gate: **pass**
- app_start_time_ms p95: **830.96 ms**
- dashboard_ttfb_ms p95: **41.64 ms**
- api_summary_latency_ms p95: **3.91 ms**

## CI-Integration
Workflow `KUKANILEA CI` enthält jetzt den optionalen Job `perf-kpi-gate` mit klarer Skip-Policy:
- Standard: Skip mit expliziter Begründung.
- Aktivierung: `workflow_dispatch` Input `run_perf_gate=true` oder Repo-Variable `CI_PERF_GATE=1`.
- Bei Aktivierung:
  1. `python scripts/perf/benchmark_gate.py --samples 3`
  2. `pytest -q tests/perf`

## Regressionstests
Es wurden mindestens zwei gezielte Degradierungs-Guards ergänzt:
1. Dashboard-Latenz-Spike => Gate muss `fail` liefern.
2. API-Summary-Latenz-Spike => Gate muss `fail` liefern.

Zusätzlich decken weitere Tests Aggregation, pass/warn-Logik und Artefakt-Output ab.

## Hard-Gates Check
- MIN_SCOPE: erfüllt (>=8 Dateien / >=220 LOC)
- MIN_TESTS: erfüllt (6 Tests in `tests/perf`)
- CI_GATE: erfüllt (`pytest -q tests/perf` integriert)
- Evidence: erfüllt (dieses Dokument)
