# KUKANILEA Main Stability Pass 1 (2026-03-07)

## Kontext
- Basis: `origin/main` @ `7d52510`
- Branch: `codex/2026-03-07-main-stability-pass1`
- Ziel: reproduzierbare Stabilisierung von Guardrails, Healthcheck und Vollsuite

## Reparaturen
1. `app/core/logic.py`
- Verhindert Background-Thread-Sturm bei `index_warmup()` durch Singleton-Startlogik.
- Hintergrundindexierung startet nur, wenn kein aktiver Warmup-Thread läuft.

2. `scripts/dev/pr_quality_guard.sh`
- Entfernt `mapfile`-Abhängigkeit (Bash-4-only) zugunsten portabler `while read`-Loops.

3. `scripts/dev/doctor.sh`
- Ersetzt `${var,,}` durch portable Lowercase-Normalisierung via `tr`.

4. `scripts/dev/open_pr_status.sh`
- Robuste Python-Interpreter-Wahl (`python3` bevorzugt, Fallback `python`).

5. `app/__init__.py`
- Stabilisiert pytest-Kontext bei lokal persistiertem `trial_expired`-State, ohne explizite Read-only-Testfälle auszuhebeln.

6. `tests/test_ingestion_integration.py`
- Regressionstest für den Warmup-Thread-Guard.

## Validierung
- `python scripts/ops/verify_guardrails.py` -> PASS
- `bash scripts/ops/healthcheck.sh` -> PASS
- `pytest -q` -> PASS (`704 passed`)
- `pytest -q tests/test_pr_quality_guard.py` -> PASS

## Ergebnis
- Bekannter Suite-Hänger um `test_trust_safety_ux_audit_runs_2200_plus_actions` ist im Volllauf behoben.
- PR-Qualitäts- und Plattformskript-Stabilität auf macOS/Bash3 wurde verbessert.

## Risiko / Rollback
- Risiko: niedrig (eng begrenzte Guard-/Script-/Thread-Änderungen).
- Rollback: Revert des Commits `9d31b20` (plus Folgecommit dieses Reports).
