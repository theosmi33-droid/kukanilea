# DEV_CI Lane Report

## Preflight
- Open-PR/Overlap-Check konnte lokal nur eingeschränkt ausgeführt werden (kein `gh`, kein `origin`-Remote im Workspace).
- Lokal verifizierter Scope: ausschließlich DEV_CI-Allowlist-Dateien wurden geändert.

## Before → After (Developer Experience)

### 1) One-command dev start
- **Before:** `scripts/dev_run.sh` installierte nur `requirements.txt`, seedete immer und startete direkt; keine Bootstrap-Kopplung.
- **After:** `scripts/dev_run.sh` nutzt standardmäßig `.venv`, erkennt Bootstrap-Status über `.venv/.bootstrap_complete`, führt bei Bedarf `scripts/dev_bootstrap.sh` automatisch aus und bietet Flags `--skip-bootstrap`, `--skip-seed`, `--host`, `--port`.

### 2) Healthcheck gegen Interpreter-Drift
- **Before:** Healthcheck nahm `PYTHON` an, ohne Drift-Absicherung gegen `.venv`.
- **After:** `scripts/ops/healthcheck.sh` bricht mit klarer Fehlermeldung ab, wenn `.venv/bin/python` existiert, aber ein anderer Interpreter genutzt wird.

### 3) CI Queue Dedup + stabile Required Checks
- **Before:** Alle Workflows nutzten `cancel-in-progress: true` auch für Pushes.
- **After:** `cancel-in-progress` ist auf Pull-Requests begrenzt. PR-Läufe bleiben dedupliziert; Push-Läufe (z. B. main-required checks) werden nicht mehr aggressiv weggekürzt.

### 4) Timestamp-Dokumentflut reduziert
- **Before:** `launch_evidence_gate.sh` erzeugte pro Lauf neue timestamped Dateien.
- **After:** Standardausgabe auf stabile Dateien `docs/reviews/codex/LAUNCH_EVIDENCE_RUN.md` und `docs/reviews/codex/LAUNCH_DECISION.md` umgestellt.
