# Scope Request: Gemini Base Operator Fixes 2026-03-06

## Context
Stabilisierung der Test-Suite und Shell-Skripte im `kukanilea_production` Repository nach Branch-Sync auf `main`.

## Gefundene Probleme
1. **KeyError: 'envelope'**: Integration-Tests schlugen fehl, da die Lizenzprüfung (`trial_expired`) Schreibzugriffe blockierte.
2. **Bash-Inkompatibilität**: `scripts/dev/doctor.sh` nutzte `${1,,}`, was in der Standard-Bash von macOS (3.2) zu Fehlern führt.

## Durchgeführte Änderungen
- **app/__init__.py**: `READ_ONLY` wird im Test-Kontext (`_is_test_context`) explizit auf `False` gesetzt.
- **scripts/dev/doctor.sh**: Ersetzung von `${1,,}` durch `$(echo "$1" | tr '[:upper:]' '[:lower:]')` für breitere Kompatibilität.

## Requested Scope
- Freigabe der Änderungen in `app/__init__.py` (Shared-Core).
- Freigabe der Änderungen in `scripts/dev/doctor.sh`.
- Akzeptanz der Test-Suite-Stabilisierung.

## Evidence
- `tests/integration/test_flow_ab_2000x.py`: PASS
- `tests/ops/test_doctor_playwright_checks.py`: PASS
- Alle Domaenen-Tests (`tests/domain/`): PASS
- Alle Integration-Tests (`tests/integration//`): PASS
- Alle E2E-Tests (`tests/e2e/`): PASS
- (Hinweis: Tests erfordern `PYENV_VERSION=3.12.0` in lokaler Umgebung)
