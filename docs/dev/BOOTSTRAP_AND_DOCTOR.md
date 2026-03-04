# Bootstrap & Doctor (Developer Platform Hardening)

Dieses Dokument ist die verbindliche Referenz für lokale Entwicklung und CI-Basischecks.
Die Befehle sind **identisch** zu den Targets in `Makefile` und zur README.

## 1) Bootstrap

```bash
make bootstrap
```

`./scripts/bootstrap.sh` ist idempotent und führt aus:

1. Python-Version gegen `.python-version` prüfen (klarer Fehler bei Mismatch).
2. `.build_venv` erstellen oder wiederverwenden.
3. `requirements.txt` + `requirements-dev.txt` installieren.
4. Playwright Browser installieren (`python -m playwright install chromium`).
5. `pre-commit install --install-hooks`.

## 2) Doctor

```bash
make doctor
./scripts/doctor.sh --json
```

Checks in `scripts/doctor.sh`:

- `python-version`
- `python`
- `pip`
- `venv`
- `sqlite3`
- `rg`
- `gh`
- `playwright`
- `.build_venv`

Exit Codes:

- `0`: alles OK
- `2`: mindestens ein Check fehlgeschlagen
- `64`: ungültige Argumente

## 3) Test Corridor

```bash
make test-smoke
make test-full
```

- `test-smoke`: schnelle Gate-Checks (Doctor + gezielte Tests)
- `test-full`: vollständige Test-Suite (`pytest -q`)
