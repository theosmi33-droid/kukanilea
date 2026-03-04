# ENV_FOUNDATION Final Report (20260304_201322)

## Zielbild
ENV_FOUNDATION_1000 sollte die Umgebung so stabilisieren, dass fehlende Python-Tools (`pytest`, `flask`, `ruff`, `playwright`) nicht mehr durch Interpreter-Drift entstehen und lokale Ausführung an CI-Kommandos angeglichen ist.

## Umgesetzte Änderungen
1. **Python-Toolchain fixiert**
   - `.python-version` auf `3.12.12` gestellt (vorher `3.12.0`, in diesem Host nicht installiert).
   - Neuer Bootstrap: `scripts/ops/env_foundation_setup.sh` (pyenv-aware, `.build_venv`, requirements + dev requirements + playwright-browser install).

2. **Healthcheck robuster gegen Interpreter-Drift**
   - `scripts/ops/healthcheck.sh` nutzt jetzt `choose_python()` mit deterministischer Reihenfolge:
     - `$PYTHON` (falls gesetzt)
     - `.build_venv/bin/python`
     - `.venv/bin/python`
     - `python3`
     - `python`
   - Zusätzliche Dependency-Signale für `ruff` und `playwright` (CI = fail, lokal = warning).

3. **launch_evidence_gate robuster gegen Git-Edge-Cases**
   - Repo/CI Evidence nutzt `refs/remotes/origin/main^{commit}` mit `git rev-parse --verify --quiet`, wodurch der frühere Fehler `fatal: Needed a single revision` nicht mehr auftritt.

4. **CI-Parity lokal hergestellt (Command-Parity Script)**
   - Neues Script `scripts/ops/ci_parity_local.sh` bildet Kernschritte aus GitHub Actions nach:
     - Compile sanity
     - VSCode config policy check
     - pytest ohne e2e
     - selected core tests
     - Playwright e2e-run mit fallback `--lf`

5. **Action Ledger >=1000**
   - Dokument angelegt: `docs/reviews/codex/ACTION_LEDGER_ENV_FOUNDATION_20260304_201322.md` mit 1005 Action-Einträgen.

## Gate-Runs (Pflicht)
### Vorher
- `bash scripts/dev/vscode_guardrails.sh --check` ✅
- `bash scripts/orchestration/overlap_matrix_11.sh` ✅
- `./scripts/ops/healthcheck.sh` ✅ (mit Warnungen wegen fehlender Pakete im gewählten Interpreter)
- `scripts/ops/launch_evidence_gate.sh` ❌ (Exit 4 / NO-GO durch Gate-Fails)

### Nachher
- `bash scripts/dev/vscode_guardrails.sh --check` ✅
- `bash scripts/orchestration/overlap_matrix_11.sh` ✅
- `./scripts/ops/healthcheck.sh` ✅ (Interpreter now `.build_venv/bin/python`, aber weiterhin Warnungen bei nicht installierten Paketen)
- `scripts/ops/launch_evidence_gate.sh` ❌ (Exit 4 bleibt möglich wegen inhaltlicher Gate-Fails, aber **ohne** git revision fatal)

## Aktueller Blocker
Die vollständige Paketinstallation (`requirements.txt`, `requirements-dev.txt`, `playwright install --with-deps chromium`) ist in dieser Session durch Netzwerk/Proxy-Limit blockiert:
- Proxy-Pfad liefert `403 Forbidden` auf pip index Zugriff.
- Direktzugriff ohne Proxy liefert `Network is unreachable`.

Damit ist die **Script- und Toolchain-Grundlage** implementiert, aber die **vollständige Dependency-Hydration** in diesem Lauf technisch nicht abschließbar.

## Nächster operativer Schritt
Sobald Netzwerk auf PyPI + Playwright CDN/Deps verfügbar ist:
1. `scripts/ops/env_foundation_setup.sh`
2. `./scripts/ops/healthcheck.sh --ci`
3. `scripts/ops/ci_parity_local.sh`
4. `scripts/ops/launch_evidence_gate.sh`

Danach sollte die Zielaussage „nie wieder fehlt pytest/flask/ruff/playwright“ praktisch verifiziert werden.
