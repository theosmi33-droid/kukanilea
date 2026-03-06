# Gate 7 Testmatrix (Evidence-first)

## Zielkriterien aus Launch-Evidence-Checklist

| Gate-7-Kriterium | Testfall-ID | Implementierung | Evidence-Artefakt | Status |
|---|---|---|---|---|
| Lokales Modell aktiv (inkl. Fallback) | G7-01 | `scripts/ops/gate7_evidence.py` prüft `get_default_provider().name in {mock, ollama}` | `evidence/operations/gate7_latest/gate7_smoke.json` (`lokales_modell_aktiv`) | PASS |
| Summary/Read APIs funktionieren | G7-02 | Read-Route: `ManagerAgent.route("Bitte zeige dashboard status")` muss `dashboard_summary` + `mode=read` liefern | `evidence/operations/gate7_latest/gate7_smoke.json` (`summary_read_api_ok`) | PASS |
| Jede Write-Aktion braucht Confirm-Gate | G7-03 | Write ohne Confirm muss `confirm_required` liefern | `evidence/operations/gate7_latest/gate7_smoke.json` (`write_confirm_gate_erzwungen`) | PASS |
| Write mit expliziter Bestätigung erlaubt | G7-04 | Write mit `confirm=yes` muss auf `routed` gehen | `evidence/operations/gate7_latest/gate7_smoke.json` (`write_mit_confirm_moeglich`) | PASS |
| Audit-Logs vorhanden | G7-05 | `EventBus` muss Events (`confirm_blocked`, `routed`, `blocked`) enthalten, `audit_logger` muss synchron mitschreiben | `evidence/operations/gate7_latest/gate7_smoke.json` (`audit_logs_vorhanden`) | PASS |
| Injection-Eingaben lösen keine unkontrollierte Aktion aus | G7-06 | Injection-ähnlicher Prompt muss auf `blocked` + `safe_fallback` enden | `evidence/operations/gate7_latest/gate7_smoke.json` (`injection_blockiert`) | PASS |

## Reproduzierbare Befehle

```bash
python3 -m pytest -q tests/ops/test_gate7_evidence_smoke.py tests/ops/test_gate7_launch_evidence_contract.py
python3 scripts/ops/gate7_evidence.py --output-dir evidence/operations/gate7_latest
scripts/ops/launch_evidence_gate.sh --skip-healthcheck --out docs/reviews/codex/LAUNCH_GATE_AUTOMATION_REPORT_gate7.md --json-out docs/reviews/codex/LAUNCH_GATE_AUTOMATION_REPORT_gate7.json
```

## NO-GO-Bewertung (gesamt)

Gate 7 selbst ist in der Smoke-Evidence PASS. Gesamt-Launch bleibt dennoch **NO-GO/FAIL**, weil andere harte Gates im Launch-Gate-Run fehlschlagen (`License`, `Backup`, `Evidence path contract`).
